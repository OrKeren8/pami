"""Endpoints for the other services, not for browsers.

The AI service holds no membership data of its own, so it asks here whether a user may see a
project. Reading the projects collection directly would work - the services share a database -
but it would couple the AI service to this service's schema, so the next change to how
membership is stored would silently break authorization somewhere else.

Authenticated with the shared service key, because the callers include background tasks with
no user request in flight.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from projects_service.core.auth import ServiceCallerDep
from projects_service.data.project_repository import ProjectRepository
from projects_service.core.access import pre_migration_caller_id
from projects_service.dependencies import get_project_repository

router = APIRouter(prefix="/internal", tags=["internal"])


class AccessCheckRequest(BaseModel):
    user_id: str
    project_id: str


class AccessCheckResponse(BaseModel):
    allowed: bool


@router.post("/authz/check", response_model=AccessCheckResponse)
async def check_project_access(
    request: AccessCheckRequest,
    caller: ServiceCallerDep,
    projects: ProjectRepository = Depends(get_project_repository),
):
    """Whether this user is a member of this project."""
    project = await projects.get_by_id(request.project_id)
    if not project:
        return AccessCheckResponse(allowed=False)
    if request.user_id in project.member_ids():
        return AccessCheckResponse(allowed=True)

    # The same allowance GET /projects/ makes, and it has to be the same or the two
    # disagree: that service showed the stand-in user its un-migrated projects while
    # this one refused them, so the graph listed a project whose conversations could
    # not be opened.
    if not project.members and pre_migration_caller_id(request.user_id):
        return AccessCheckResponse(allowed=True)

    return AccessCheckResponse(allowed=False)
