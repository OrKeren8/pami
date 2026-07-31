"""Cognito JWT verification.

The token is verified locally against the pool's published JWKS rather than by calling
Cognito on every request: a network round trip per request would double the latency of every
endpoint and make the API unavailable whenever Cognito is slow. The signing keys rotate
rarely, so they are fetched once and cached.

Nothing here trusts a client-supplied identity. The subject and email come only from a
signature-verified token, which is what makes ownership checks meaningful - a caller cannot
claim to be someone else by setting a header.
"""

from typing import Annotated, Any, Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from jwt import PyJWKClient
from jwt import decode as jwt_decode
from jwt.exceptions import PyJWTError
from loguru import logger

from projects_service.core.config import settings

_logger = logger.bind(component="auth")

# One client per process. PyJWKClient caches the fetched keys and only re-fetches when it
# sees a key id it does not know, which is exactly the rotation case.
_jwk_client: Optional[PyJWKClient] = None


class AuthenticatedUser:
    """The caller, as proven by their token."""

    def __init__(self, user_id: str, email: Optional[str], groups: list[str]):
        self.user_id = user_id
        self.email = (email or "").lower() or None
        self.groups = groups

    @property
    def is_admin(self) -> bool:
        """Admin rights come from the token, never from a request field.

        Both an email allowlist and a Cognito group are accepted: the group is the right
        long-term answer, but group management needs IAM permissions that a restricted lab
        account may not have, and the allowlist works with no AWS setup at all.
        """
        if settings.admin_group and settings.admin_group in self.groups:
            return True
        return bool(self.email) and self.email in settings.admin_email_list

    def __repr__(self) -> str:
        return f"AuthenticatedUser(user_id={self.user_id!r}, email={self.email!r})"


def _issuer() -> str:
    return (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}"
    )


def _jwks_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = PyJWKClient(f"{_issuer()}/.well-known/jwks.json")
    return _jwk_client


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _claims_of(token: str) -> dict[str, Any]:
    """Verified claims, or a 401. Never returns unverified data.

    Verifies the ID token specifically. Sharing a project by email and the admin gate both
    need the `email` claim, which Cognito puts on the id token and not on the access token -
    accepting either would mean those features silently had no email to work with.
    """
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt_decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=_issuer(),
            # `aud` is only present on an id token; an access token carries `client_id`
            # instead, so it is checked separately below rather than here.
            options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
            # Cognito and the container clock can differ by a second or two, which would
            # otherwise reject a token that was just issued.
            leeway=30,
        )
    except PyJWTError as error:
        _logger.info(f"Rejected token: {type(error).__name__}: {error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (httpx.HTTPError, OSError) as error:
        # The keys could not be fetched. This is our failure, not the caller's, and
        # answering 401 would look like their token was bad and send them to log in again.
        _logger.error(f"Could not fetch Cognito signing keys: {type(error).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable",
        )

    if claims.get("token_use") != "id":
        _logger.info(
            f"Rejected {claims.get('token_use')!r} token: an id token is required"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_client = settings.cognito_client_id
    if expected_client:
        presented = claims.get("aud") or claims.get("client_id")
        if presented != expected_client:
            _logger.info("Rejected token issued for a different app client")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # An unverified address must not be usable: sign-up is open, so anyone could otherwise
    # register someone else's email and be handed the projects shared with it - or the admin
    # page.
    if claims.get("email") and claims.get("email_verified") is False:
        _logger.warning(f"Rejected token for unverified email {claims.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please confirm your email address before signing in",
        )

    return claims


def _user_from_claims(claims: dict[str, Any]) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(claims.get("sub")),
        email=claims.get("email") or claims.get("username"),
        groups=list(claims.get("cognito:groups") or []),
    )


async def current_user(request: Request) -> AuthenticatedUser:
    """The authenticated caller. 401 when there is no valid token.

    With `auth_required` off, a request with no token is answered as the local development
    user instead of rejected. That switch exists so this can be deployed before a user pool
    exists without taking the running app offline; it must be on in any real deployment.
    """
    token = _bearer_token(request)

    if token:
        # PyJWKClient does a blocking HTTPS fetch the first time it sees a key id, which
        # would stall the whole event loop on a cold start or a key rotation.
        claims = await run_in_threadpool(_claims_of, token)
        return _user_from_claims(claims)

    if not settings.auth_required:
        return AuthenticatedUser(
            user_id=settings.unauthenticated_user_id,
            email=settings.unauthenticated_user_email,
            groups=[],
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_admin(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
) -> AuthenticatedUser:
    """Admin-only endpoints. Enforced here, not in the UI, which can only hide a link."""
    if not user.is_admin:
        _logger.warning(f"Admin endpoint refused for {user.email or user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user


CurrentUserDep = Annotated[AuthenticatedUser, Depends(current_user)]
CurrentAdminDep = Annotated[AuthenticatedUser, Depends(current_admin)]


async def prime_signing_keys() -> bool:
    """Fetch the pool's signing keys at startup so the first request does not pay for it.

    Warns rather than raises: a pool that is briefly unreachable must not stop the container
    from booting, because a container that never becomes healthy is rolled back and the
    deploy fails for a reason unrelated to the code.
    """
    if not settings.cognito_user_pool_id:
        _logger.info("No Cognito user pool configured; token verification is idle")
        return False
    try:
        await run_in_threadpool(_jwks_client().get_signing_keys)
        _logger.info(
            f"Cognito signing keys loaded for pool {settings.cognito_user_pool_id}"
        )
        return True
    except Exception as error:
        _logger.warning(
            f"Could not preload Cognito signing keys ({type(error).__name__}); "
            f"they will be fetched on first use"
        )
        return False
