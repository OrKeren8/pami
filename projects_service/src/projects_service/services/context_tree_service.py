from typing import List, Optional
from datetime import datetime
from loguru import logger
import uuid
import aiohttp

from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.models.context_tree import ContextTreeNode
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
)
from projects_service.core.config import settings


class ContextTreeService:
    """Service for context tree business logic."""

    def __init__(self, context_tree_repository: ContextTreeRepository):
        self._logger = logger.bind(service="ContextTreeService")
        self._context_tree_repository = context_tree_repository

    async def create_node(
        self, project_id: str, request: CreateContextTreeNodeRequest
    ) -> ContextTreeNodeResponse:
        """Create a new context tree node."""
        # Create domain model from request
        node = ContextTreeNode(
            parent_id=request.parent_id,
            children_ids=request.children_ids,
            text=request.text,
            summary=request.summary,
            topics=request.topics,
            project_id=project_id,
            node_type=request.node_type,
        )
        created_node = await self._context_tree_repository.create(node)

        # Create AI conversation for this node
        conversation_id = await self._create_ai_conversation(
            str(created_node.id), project_id
        )
        if conversation_id:
            created_node.conversation_id = conversation_id
            await created_node.save()
            self._logger.info(
                f"Created AI conversation {conversation_id} for node {created_node.id}"
            )

            # Let AI organize the node in the tree
            await self._ai_organize_node(created_node, project_id, conversation_id)

        # If the node has a parent, update the parent's children list
        if request.parent_id:
            parent_node = await self._context_tree_repository.get_by_id(
                request.parent_id
            )
            if parent_node:
                # Add the new child to parent's children_ids if not already present
                if created_node.id not in parent_node.children_ids:
                    parent_node.children_ids.append(created_node.id)
                    await parent_node.save()
                    self._logger.info(
                        f"Updated parent {request.parent_id} to include child {created_node.id}"
                    )

        return ContextTreeNodeResponse(
            id=str(created_node.id),
            parent_id=created_node.parent_id,
            children_ids=created_node.children_ids,
            text=created_node.text,
            summary=created_node.summary,
            topics=created_node.topics,
            project_id=created_node.project_id,
            node_type=created_node.node_type,
            conversation_id=created_node.conversation_id,
            created_at=created_node.created_at,
            updated_at=created_node.updated_at,
        )

    async def _create_ai_conversation(
        self, context_node_id: str, project_id: str
    ) -> Optional[str]:
        """Create an AI conversation for a context node."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.ai_service_url}/ai/ai-conversations/",
                    json={
                        "context_node_id": context_node_id,
                        "project_id": project_id,
                        "title": f"AI Discussion - Node {context_node_id[:8]}",
                    },
                ) as response:
                    if response.status == 200:
                        return (await response.json()).get("conversation_id")
                    else:
                        text = await response.text()
                        self._logger.error(
                            f"Failed to create AI conversation: {response.status} - {text}"
                        )
                        return None
        except Exception as e:
            self._logger.error(f"Error calling AI service: {e}")
            return None

    async def _ai_organize_node(
        self, node: ContextTreeNode, project_id: str, conversation_id: str
    ) -> None:
        """Request AI to analyze and organize node in the tree."""
        try:
            # Get all nodes in the project for context
            all_nodes = await self._context_tree_repository.list_by_project(project_id)

            # Build tree context (exclude the current node since it's new)
            tree_context = [
                {
                    "id": str(n.id),
                    "parent_id": n.parent_id,
                    "text": n.text,
                    "summary": n.summary,
                    "topics": n.topics,
                    "node_type": n.node_type,
                }
                for n in all_nodes
                if str(n.id) != str(node.id)
            ]

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.ai_service_url}/ai/tree-analysis/organize-node",
                    json={
                        "node_id": str(node.id),
                        "conversation_id": conversation_id,
                        "current_tree": tree_context,
                    },
                ) as response:
                    if response.status == 200:
                        ai_suggestion = await response.json()
                        self._logger.info(
                            f"AI suggested organization for node {node.id}: {ai_suggestion.get('reasoning')}"
                        )

                        # Update node with AI suggestions
                        node.summary = ai_suggestion.get("summary", node.summary)
                        node.topics = ai_suggestion.get("topics", node.topics)
                        suggested_parent = ai_suggestion.get("suggested_parent_id")

                        # Update parent if AI suggests a different one
                        if suggested_parent and suggested_parent != node.parent_id:
                            # Remove from old parent's children
                            if node.parent_id:
                                old_parent = (
                                    await self._context_tree_repository.get_by_id(
                                        node.parent_id
                                    )
                                )
                                if (
                                    old_parent
                                    and str(node.id) in old_parent.children_ids
                                ):
                                    old_parent.children_ids.remove(str(node.id))
                                    await old_parent.save()

                            # Set new parent
                            node.parent_id = suggested_parent

                            # Add to new parent's children
                            new_parent = await self._context_tree_repository.get_by_id(
                                suggested_parent
                            )
                            if (
                                new_parent
                                and str(node.id) not in new_parent.children_ids
                            ):
                                new_parent.children_ids.append(str(node.id))
                                await new_parent.save()

                        await node.save()
                        self._logger.info(f"Updated node {node.id} with AI suggestions")
                    else:
                        text = await response.text()
                        self._logger.error(
                            f"Failed to get AI organization: {response.status} - {text}"
                        )
        except Exception as e:
            self._logger.error(f"Error requesting AI organization: {e}")
            # Don't fail the whole operation if AI organization fails

    async def get_node(self, node_id: str) -> Optional[ContextTreeNodeResponse]:
        """Get a context tree node by its node_id."""
        node = await self._context_tree_repository.get_by_id(node_id)
        if not node:
            return None

        return ContextTreeNodeResponse(
            id=str(node.id),
            parent_id=node.parent_id,
            children_ids=node.children_ids,
            text=node.text,
            summary=node.summary,
            topics=node.topics,
            project_id=node.project_id,
            node_type=node.node_type,
            conversation_id=node.conversation_id,
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
                parent_id=n.parent_id,
                children_ids=n.children_ids,
                text=n.text,
                summary=n.summary,
                topics=n.topics,
                project_id=n.project_id,
                node_type=n.node_type,
                conversation_id=n.conversation_id,
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
            parent_id=node.parent_id,
            children_ids=node.children_ids,
            text=node.text,
            summary=node.summary,
            topics=node.topics,
            project_id=node.project_id,
            node_type=node.node_type,
            conversation_id=node.conversation_id,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    async def delete_node(self, node_id: str) -> bool:
        """Delete a context tree node."""
        return await self._context_tree_repository.delete(node_id)
