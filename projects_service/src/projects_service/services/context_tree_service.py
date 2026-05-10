from typing import List, Optional
from datetime import datetime
from loguru import logger
import uuid

from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.models.context_tree import ContextTreeNode
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
)


class ContextTreeService:
    """Service for context tree business logic."""

    def __init__(self, context_tree_repository: ContextTreeRepository):
        self._logger = logger.bind(service="ContextTreeService")
        self._context_tree_repository = context_tree_repository

    async def create_node(
        self, project_id: str, request: CreateContextTreeNodeRequest
    ) -> ContextTreeNodeResponse:
        """Create a new context tree node."""
        # Always generate a unique node_id
        node_id = str(uuid.uuid4())

        # Create domain model from request
        node = ContextTreeNode(
            node_id=node_id,
            parent_id=request.parent_id,
            children_ids=request.children_ids,
            text=request.text,
            project_id=project_id,
            node_type=request.node_type,
        )
        created_node = await self._context_tree_repository.create(node)

        # If the node has a parent, update the parent's children list
        if request.parent_id:
            parent_node = await self._context_tree_repository.get_by_id(
                request.parent_id
            )
            if parent_node:
                # Add the new child to parent's children_ids if not already present
                if node_id not in parent_node.children_ids:
                    parent_node.children_ids.append(node_id)
                    await self._context_tree_repository.update(parent_node)
                    self._logger.info(
                        f"Updated parent {request.parent_id} to include child {node_id}"
                    )

        return ContextTreeNodeResponse(
            id=str(created_node.id),
            node_id=created_node.node_id,
            parent_id=created_node.parent_id,
            children_ids=created_node.children_ids,
            text=created_node.text,
            project_id=created_node.project_id,
            node_type=created_node.node_type,
            created_at=created_node.created_at,
            updated_at=created_node.updated_at,
        )

    async def get_node(self, node_id: str) -> Optional[ContextTreeNodeResponse]:
        """Get a context tree node by its node_id."""
        node = await self._context_tree_repository.get_by_id(node_id)
        if not node:
            return None

        return ContextTreeNodeResponse(
            id=str(node.id),
            node_id=node.node_id,
            parent_id=node.parent_id,
            children_ids=node.children_ids,
            text=node.text,
            project_id=node.project_id,
            node_type=node.node_type,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    async def list_nodes_by_project(
        self, project_id: str
    ) -> List[ContextTreeNodeResponse]:
        """List all context tree nodes for a project."""
        nodes = await self._context_tree_repository.list_by_project(project_id)
        return [
            ContextTreeNodeResponse(
                id=str(n.id),
                node_id=n.node_id,
                parent_id=n.parent_id,
                children_ids=n.children_ids,
                text=n.text,
                project_id=n.project_id,
                node_type=n.node_type,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in nodes
        ]

    async def update_node(
        self, node_id: str, request: UpdateContextTreeNodeRequest
    ) -> Optional[ContextTreeNodeResponse]:
        """Update a context tree node."""
        update_data = request.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        node = await self._context_tree_repository.update(node_id, update_data)
        if not node:
            return None

        return ContextTreeNodeResponse(
            id=str(node.id),
            node_id=node.node_id,
            parent_id=node.parent_id,
            children_ids=node.children_ids,
            text=node.text,
            project_id=node.project_id,
            node_type=node.node_type,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    async def delete_node(self, node_id: str) -> bool:
        """Delete a context tree node."""
        return await self._context_tree_repository.delete(node_id)
