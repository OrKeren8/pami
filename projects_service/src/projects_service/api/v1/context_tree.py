from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from typing import List
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
    UpdateSiblingScoresRequest,
)
from projects_service.services.context_tree_service import (
    ContextTreeService,
    ConversationPurgeError,
    UnknownSiblingError,
)
from projects_service.dependencies import (
    ContextTreeServiceDep,
    get_context_tree_service,
)
from projects_service.core.access import NodeForMemberDep, ProjectForMemberDep
from projects_service.core.auth import ServiceCallerDep

router = APIRouter(prefix="/context-tree", tags=["context-tree"])


@router.post("/projects/{project_id}/nodes", response_model=ContextTreeNodeResponse)
async def create_node(
    request: CreateContextTreeNodeRequest,
    project: ProjectForMemberDep,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    return await service.create_node(str(project.id), request)


@router.get(
    "/projects/{project_id}/nodes", response_model=List[ContextTreeNodeResponse]
)
async def list_nodes(
    project: ProjectForMemberDep,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    return await service.list_nodes_by_project(str(project.id))


@router.get("/nodes/{node_id}", response_model=ContextTreeNodeResponse)
async def get_node(
    node: NodeForMemberDep,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    found = await service.get_node(str(node.id))
    if not found:
        raise HTTPException(status_code=404, detail="Node not found")
    return found


@router.put("/nodes/{node_id}/sibling-scores", response_model=ContextTreeNodeResponse)
async def update_sibling_scores(
    node_id: str,
    request: UpdateSiblingScoresRequest,
    context_tree_service: ContextTreeServiceDep,
    caller: ServiceCallerDep,
):
    """Apply externally computed sibling correlation scores to a node.

    Called by the AI service, not a browser: the scoring runs from a background task with no
    user request in flight, so this authenticates a peer service rather than a person.
    """
    try:
        node = await context_tree_service.apply_sibling_scores(
            node_id, request.scores, request.source, request.near_peers
        )
    except UnknownSiblingError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.put("/nodes/{node_id}", response_model=ContextTreeNodeResponse)
async def update_node(
    request: UpdateContextTreeNodeRequest,
    node: NodeForMemberDep,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    updated = await service.update_node(str(node.id), request)
    if not updated:
        raise HTTPException(status_code=404, detail="Node not found")
    return updated


@router.delete("/nodes/{node_id}")
async def delete_node(
    node: NodeForMemberDep,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    node_id = str(node.id)
    try:
        deleted = await service.delete_node(node_id)
    except ConversationPurgeError as error:
        # Reported rather than swallowed: the node still exists, so the client can retry
        # instead of believing the content is gone while it stays searchable.
        logger.error(f"Node {node_id} kept because its conversation survived: {error}")
        raise HTTPException(
            status_code=503,
            detail="The node's conversation could not be removed. Nothing was deleted; please try again.",
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"message": "Node deleted"}
