"""Project access checks, as dependencies.

Every project-scoped resource in this service is reached by a `project_id` the client
supplies. Without a check here, passing someone else's project id is all it takes to read or
write their data - the endpoints themselves never doubted the id. These dependencies are the
single place that doubt lives.

404 rather than 403 for a project the caller cannot see: 403 confirms the project exists,
which is itself information the caller is not entitled to.
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from loguru import logger

from projects_service.core.auth import AuthenticatedUser, current_user
from projects_service.dependencies import (
    get_context_tree_repository,
    get_project_repository,
    get_task_repository,
)
from projects_service.data.project_repository import ProjectRepository
from projects_service.models.project import Project, ProjectRole

_logger = logger.bind(component="access")

NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
)


async def _load_visible_project(
    project_id: str, user: AuthenticatedUser, repository: ProjectRepository
) -> Project:
    project = await repository.get_by_id(project_id)
    if not project:
        raise NOT_FOUND

    if user.user_id not in project.member_ids():
        # Includes the un-migrated case: a project with no members belongs to nobody and is
        # visible to nobody, rather than defaulting to visible to everybody.
        _logger.info(
            f"Refused project {project_id} for {user.email or user.user_id}: not a member"
        )
        raise NOT_FOUND
    return project


async def project_for_member(
    project_id: str,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> Project:
    """The project, if the caller is a member of it."""
    return await _load_visible_project(project_id, user, repository)


async def project_for_owner(
    project_id: str,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> Project:
    """The project, if the caller owns it.

    Renaming, deleting, inviting and removing are owner-only: a member who could invite could
    hand the owner's project to anyone, and a member who could delete could destroy work that
    is not theirs.
    """
    project = await _load_visible_project(project_id, user, repository)
    if project.role_of(user.user_id) != ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can do this",
        )
    return project


async def project_id_for_member(
    project: Annotated[Project, Depends(project_for_member)],
) -> str:
    """Just the id, for handlers that only needed it to scope a query."""
    return str(project.id)


def visible_project_ids(projects: list[Project], user_id: str) -> set[str]:
    return {str(project.id) for project in projects if user_id in project.member_ids()}


async def assert_can_access_project(
    project_id: Optional[str], user: AuthenticatedUser, repository: ProjectRepository
) -> Project:
    """For call sites that are not route dependencies (nested resources, internal checks)."""
    if not project_id:
        raise NOT_FOUND
    return await _load_visible_project(project_id, user, repository)


async def node_for_member(
    node_id: str,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    projects: Annotated[ProjectRepository, Depends(get_project_repository)],
    nodes=Depends(get_context_tree_repository),
):
    """A context node, if the caller may see the project it belongs to.

    Node ids are handed out in graph payloads, so "I know the id" cannot be the check. The
    node's own project_id is authoritative here - never one supplied by the caller.
    """
    node = await nodes.get_by_id(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Node not found"
        )
    await _load_visible_project(str(getattr(node, "project_id", "")), user, projects)
    return node


async def task_for_member(
    task_id: str,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    projects: Annotated[ProjectRepository, Depends(get_project_repository)],
    tasks=Depends(get_task_repository),
):
    """A task, if the caller may see the project it belongs to."""
    task = await tasks.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    await _load_visible_project(str(getattr(task, "project_id", "")), user, projects)
    return task


ProjectForMemberDep = Annotated[Project, Depends(project_for_member)]
ProjectForOwnerDep = Annotated[Project, Depends(project_for_owner)]
NodeForMemberDep = Annotated[object, Depends(node_for_member)]
TaskForMemberDep = Annotated[object, Depends(task_for_member)]
