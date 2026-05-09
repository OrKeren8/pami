from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from projects_service.models.task import Task


class TaskRepository:
    """Repository for task data access."""

    def __init__(self, database: AsyncIOMotorDatabase):
        self._database = database
        self._logger = logger.bind(repository="TaskRepository")

    async def create(self, task: Task, session=None) -> Task:
        """Create a new task."""
        try:
            await task.insert(session=session)
            return task
        except Exception as e:
            self._logger.error(f"Failed to create task: {e}")
            raise

    async def get_by_id(self, task_id: str, session=None) -> Optional[Task]:
        """Get a task by ID."""
        try:
            return await Task.get(task_id, session=session)
        except Exception as e:
            self._logger.error(f"Error getting task {task_id}: {e}")
            return None

    async def list_by_project(self, project_id: str, session=None) -> List[Task]:
        """List all tasks for a project."""
        try:
            return await Task.find(
                Task.project_id == project_id, session=session
            ).to_list()
        except Exception as e:
            self._logger.error(f"Error listing tasks for project {project_id}: {e}")
            return []

    async def update(
        self, task_id: str, update_data: dict, session=None
    ) -> Optional[Task]:
        """Update a task."""
        try:
            task = await Task.get(task_id, session=session)
            if not task:
                return None

            await task.update({"$set": update_data}, session=session)
            await task.reload(session=session)
            return task
        except Exception as e:
            self._logger.error(f"Error updating task {task_id}: {e}")
            return None

    async def delete(self, task_id: str, session=None) -> bool:
        """Delete a task."""
        try:
            task = await Task.get(task_id, session=session)
            if not task:
                return False

            await task.delete(session=session)
            return True
        except Exception as e:
            self._logger.error(f"Error deleting task {task_id}: {e}")
            return False
