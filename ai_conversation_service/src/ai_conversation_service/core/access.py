"""Project access checks for the AI service.

This service holds no membership data. Every endpoint here took a `project_id` - or a
`conversation_id` that resolves to one - straight from the client and used it to read
transcripts and search vectors, so naming someone else's project was enough to read their
conversations. The check is delegated to projects-service, which owns membership.

Fails closed: if the answer cannot be obtained the request is refused, because an outage that
turned into "everyone can read everything" would be worse than an outage.
"""

import hmac
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from loguru import logger

from ai_conversation_service.core.auth import AuthenticatedUser, current_user
from ai_conversation_service.core.config import settings

_logger = logger.bind(component="access")

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _is_service_call(request: Request) -> bool:
    """Whether this is a peer service rather than a person.

    projects-service creates a node's conversation and purges it on delete, both from
    background work with no user request in flight - there is no token to forward even in
    principle. It has already checked that the user owns the project, so a valid service key
    is sufficient here.
    """
    expected = settings.service_key
    if not expected:
        return False
    presented = request.headers.get("x-service-key") or ""
    return hmac.compare_digest(presented, expected)


async def caller_identity(request: Request) -> Optional[AuthenticatedUser]:
    """The authenticated user, or None when the caller is a trusted peer service."""
    if _is_service_call(request):
        return None
    return await current_user(request)


def _projects_client(request: Request):
    service = getattr(request.app.state, "ai_conversation_service", None)
    return getattr(service, "projects_service_client", None)


async def assert_project_access(
    request: Request, user: Optional[AuthenticatedUser], project_id: Optional[str]
) -> str:
    """Confirm the caller may see this project, or 404.

    A None user means an authenticated peer service, which has already done its own
    authorization - see _is_service_call.
    """
    if not project_id:
        raise NOT_FOUND

    if user is None:
        return project_id

    client = _projects_client(request)
    if client is None:
        _logger.error("No projects client available; refusing project-scoped request")
        raise NOT_FOUND

    if not await client.can_access_project(user.user_id, project_id):
        _logger.info(f"Refused project {project_id} for {user.email or user.user_id}")
        raise NOT_FOUND
    return project_id


async def project_id_for_member(
    project_id: str,
    request: Request,
    caller: Annotated[Optional[AuthenticatedUser], Depends(caller_identity)],
) -> str:
    """A project id from the path, once membership is confirmed."""
    return await assert_project_access(request, caller, project_id)


async def conversation_for_member(
    conversation_id: str,
    request: Request,
    caller: Annotated[Optional[AuthenticatedUser], Depends(caller_identity)],
):
    """A conversation, once the caller is shown to be a member of its project.

    The conversation's own stored project_id is authoritative - never one the caller sent.
    """
    service = getattr(request.app.state, "ai_conversation_service", None)
    if service is None:
        raise NOT_FOUND

    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise NOT_FOUND

    await assert_project_access(
        request, caller, getattr(conversation, "project_id", None)
    )
    return conversation


CallerDep = Annotated[Optional[AuthenticatedUser], Depends(caller_identity)]
ProjectIdForMemberDep = Annotated[str, Depends(project_id_for_member)]
ConversationForMemberDep = Annotated[object, Depends(conversation_for_member)]
