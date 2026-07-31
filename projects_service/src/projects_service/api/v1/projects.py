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
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    service: ProjectService = Depends(get_project_service),
):
    return await service.create_project(request)


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(service: ProjectService = Depends(get_project_service)):
    return await service.list_projects()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    service: ProjectService = Depends(get_project_service),
):
    project = await service.update_project(project_id, request)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
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
