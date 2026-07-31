"""Who am I, according to my token.

The frontend needs one authoritative answer to "am I an admin", and it must come from the
server. Decoding the token in the browser would work but would mean the client deciding its
own permissions, which is the thing the admin gate exists to prevent.

Calling this also records the sign-in and claims any project invites addressed to the
caller's email.
"""

from fastapi import APIRouter, Depends

from projects_service.core.auth import CurrentUserDep
from projects_service.dependencies import get_user_directory
from projects_service.schemas.admin_schemas import SessionResponse
from projects_service.services.user_directory import UserDirectory

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/", response_model=SessionResponse)
async def start_session(
    user: CurrentUserDep,
    directory: UserDirectory = Depends(get_user_directory),
):
    claimed = 0
    if user.email:
        await directory.record_sign_in(user)
        claimed = await directory.claim_pending_invites(user)

    return SessionResponse(
        user_id=user.user_id,
        email=user.email,
        is_admin=user.is_admin,
        claimed_invites=claimed,
    )
