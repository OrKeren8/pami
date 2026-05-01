from fastapi import APIRouter, Depends, HTTPException
from typing import List
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
)
from projects_service.services.context_tree_service import ContextTreeService
from projects_service.dependencies import get_context_tree_service

router = APIRouter(prefix="/context-tree", tags=["context-tree"])


@router.post("/projects/{project_id}/nodes", response_model=ContextTreeNodeResponse)
async def create_node(
    project_id: str,
    request: CreateContextTreeNodeRequest,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    return await service.create_node(project_id, request)


@router.get(
    "/projects/{project_id}/nodes", response_model=List[ContextTreeNodeResponse]
)
async def list_nodes(
    project_id: str,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    return await service.list_nodes_by_project(project_id)


@router.get("/nodes/{node_id}", response_model=ContextTreeNodeResponse)
async def get_node(
    node_id: str,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.put("/nodes/{node_id}", response_model=ContextTreeNodeResponse)
async def update_node(
    node_id: str,
    request: UpdateContextTreeNodeRequest,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    node = await service.update_node(node_id, request)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: str,
    service: ContextTreeService = Depends(get_context_tree_service),
):
    deleted = await service.delete_node(node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"message": "Node deleted"}
