from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from projects_service.models.context_tree import ContextTreeNode


class ContextTreeRepository:
    """Repository for context tree data access."""

    def __init__(self, database: AsyncIOMotorDatabase):
        self._database = database
        self._logger = logger.bind(repository="ContextTreeRepository")

    async def create(self, node: ContextTreeNode, session=None) -> ContextTreeNode:
        """Create a new context tree node."""
        try:
            await node.insert(session=session)
            return node
        except Exception as e:
            self._logger.error(f"Failed to create context tree node: {e}")
            raise

    async def get_by_id(self, node_id: str, session=None) -> Optional[ContextTreeNode]:
        """Get a node by its id field."""
        try:
            # Try using Beanie's get (accepts ObjectId-like ids) first
            try:
                return await ContextTreeNode.get(node_id, session=session)
            except Exception:
                # Fallback: try to find by the stored `id` field or by _id
                return await ContextTreeNode.find_one({"_id": node_id}, session=session)
        except Exception as e:
            self._logger.error(f"Error getting node {node_id}: {e}")
            return None

    async def list_by_project(
        self, project_id: str, session=None
    ) -> List[ContextTreeNode]:
        """List all nodes for a project."""
        try:
            return await ContextTreeNode.find(
                ContextTreeNode.project_id == project_id, session=session
            ).to_list()
        except Exception as e:
            self._logger.error(f"Error listing nodes for project {project_id}: {e}")
            return []

    async def update(
        self, node_id: str, update_data: dict, session=None
    ) -> Optional[ContextTreeNode]:
        """Update a context tree node."""
        try:
            try:
                node = await ContextTreeNode.get(node_id, session=session)
            except Exception:
                node = await ContextTreeNode.find_one({"_id": node_id}, session=session)
            if not node:
                return None

            await node.update({"$set": update_data}, session=session)
            await node.reload(session=session)
            return node
        except Exception as e:
            self._logger.error(f"Error updating node {node_id}: {e}")
            return None

    async def delete(self, node_id: str, session=None) -> bool:
        """Delete a context tree node."""
        try:
            # Look up by the model's `id` field
            try:
                node = await ContextTreeNode.get(node_id, session=session)
            except Exception:
                node = await ContextTreeNode.find_one({"_id": node_id}, session=session)
            if not node:
                return False

            await node.delete(session=session)
            self._logger.info(f"Deleted node {node_id} from database")
            return True
        except Exception as e:
            self._logger.error(f"Error deleting node {node_id}: {e}")
            return False
