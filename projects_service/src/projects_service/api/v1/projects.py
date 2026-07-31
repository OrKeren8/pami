from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from typing import List
from projects_service.schemas.project_schemas import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
)
from projects_service.services.context_tree_service import (
    ContextTreeService,
    ConversationPurgeError,
)
from projects_service.services.project_service import ProjectService
from projects_service.services.task_service import TaskService
from projects_service.dependencies import (
    get_context_tree_service,
    get_project_service,
    get_task_service,
    get_user_directory,
)
from projects_service.core.access import ProjectForMemberDep, ProjectForOwnerDep
from projects_service.core.auth import CurrentUserDep
from projects_service.schemas.project_schemas import (
    InviteMemberRequest,
    ProjectMembersResponse,
)
from projects_service.services.user_directory import UserDirectory

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    user: CurrentUserDep,
    service: ProjectService = Depends(get_project_service),
):
    return await service.create_project(request, user.user_id, user.email)


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    user: CurrentUserDep,
    service: ProjectService = Depends(get_project_service),
    directory: UserDirectory = Depends(get_user_directory),
):
    """The caller's own projects, plus any shared with them.

    This returned every project in the database. Invites are claimed here as well as at
    sign-in, so a project shared with someone while they are already logged in shows up on
    their next refresh instead of only after signing out and back in.
    """
    await directory.claim_pending_invites(user)
    return await service.list_projects(user.user_id)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project: ProjectForMemberDep,
    service: ProjectService = Depends(get_project_service),
):
    return await service.get_project(str(project.id))


@router.get("/{project_id}/members", response_model=ProjectMembersResponse)
async def list_members(project: ProjectForMemberDep):
    """Who this project is shared with. Members can see each other."""
    return ProjectMembersResponse(
        owner_id=project.owner_id,
        members=[member.model_dump() for member in project.members],
        pending_invites=[invite.model_dump() for invite in project.pending_invites],
    )


@router.post("/{project_id}/members")
async def invite_member(
    request: InviteMemberRequest,
    project: ProjectForOwnerDep,
    service: ProjectService = Depends(get_project_service),
    directory: UserDirectory = Depends(get_user_directory),
):
    """Share a project with someone by email address."""
    existing = await directory.find_by_email(request.email)
    try:
        return await service.add_member_by_email(
            project, request.email, project.owner_id or "", existing
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.delete("/{project_id}/members/{member_id}")
async def remove_member(
    member_id: str,
    project: ProjectForOwnerDep,
    service: ProjectService = Depends(get_project_service),
):
    try:
        removed = await service.remove_member(project, member_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if not removed:
        raise HTTPException(status_code=404, detail="That person is not a member")
    return {"message": "Member removed"}


@router.delete("/{project_id}/invites/{email}")
async def cancel_invite(
    email: str,
    project: ProjectForOwnerDep,
    service: ProjectService = Depends(get_project_service),
):
    if not await service.cancel_invite(project, email):
        raise HTTPException(status_code=404, detail="No such invite")
    return {"message": "Invite cancelled"}


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    request: UpdateProjectRequest,
    project: ProjectForOwnerDep,
    service: ProjectService = Depends(get_project_service),
):
    updated = await service.update_project(str(project.id), request)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return updated


@router.delete("/{project_id}")
async def delete_project(
    project: ProjectForOwnerDep,
    service: ProjectService = Depends(get_project_service),
    context_tree_service: ContextTreeService = Depends(get_context_tree_service),
    task_service: TaskService = Depends(get_task_service),
):
    """Delete a project and everything under it.

    This used to delete one document and nothing else: the project's nodes, its tasks, its
    conversation transcripts and their search chunks all survived. Nothing referenced them
    afterwards, so they could not be cleaned up - and because retrieval filters only by
    project_id, the assistant kept quoting conversations from a project the user had deleted.
    Nodes go first, because each one removes its own conversation and refuses if that fails.
    """
    project_id = str(project.id)
    nodes = await context_tree_service.list_nodes_by_project(project_id)
    for node in nodes:
        try:
            await context_tree_service.delete_node(str(node.id))
        except ConversationPurgeError as error:
            logger.error(f"Aborting delete of project {project_id}: {error}")
            raise HTTPException(
                status_code=503,
                detail="A conversation in this project could not be removed. Nothing was deleted; please try again.",
            )

    for task in await task_service.list_tasks_by_project(project_id):
        await task_service.delete_task(str(task.id))

    deleted = await service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info(
        f"Deleted project {project_id} with {len(nodes)} nodes and their conversations"
    )
    return {"message": "Project deleted"}
