from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from projects_service.models.project import Project


class ProjectRepository:
    """Repository for project data access."""

    def __init__(self, database: AsyncIOMotorDatabase):
        self._database = database
        self._logger = logger.bind(repository="ProjectRepository")

    async def create(self, project: Project, session=None) -> Project:
        """Create a new project."""
        try:
            await project.insert(session=session)
            return project
        except Exception as e:
            self._logger.error(f"Failed to create project: {e}")
            raise

    async def get_by_id(self, project_id: str, session=None) -> Optional[Project]:
        """Get a project by ID."""
        try:
            return await Project.get(project_id, session=session)
        except Exception as e:
            # Beanie's `get` expects the document id to be a PydanticObjectId (ObjectId).
            # In some cases the stored _id might be a string (UUID) which causes validation
            # errors when calling `get`. Try a fallback lookup using `find_one` by _id.
            self._logger.warning(
                f"Project.get failed for id {project_id}: {e}. Trying fallback find_one by _id."
            )
            try:
                proj = await Project.find_one({"_id": project_id})
                if proj:
                    return proj
            except Exception as e2:
                self._logger.error(
                    f"Fallback find_one also failed for {project_id}: {e2}"
                )
            return None

    async def list_all(self, session=None) -> List[Project]:
        """List all projects."""
        try:
            return await Project.find_all(session=session).to_list()
        except Exception as e:
            self._logger.error(f"Error listing projects: {e}")
            return []

    async def update(
        self, project_id: str, update_data: dict, session=None
    ) -> Optional[Project]:
        """Update a project."""
        try:
            try:
                project = await Project.get(project_id, session=session)
            except Exception as e_get:
                self._logger.warning(
                    f"Project.get failed for update id {project_id}: {e_get}. Trying fallback find_one by _id."
                )
                project = await Project.find_one({"_id": project_id})

            if not project:
                return None

            await project.update({"$set": update_data}, session=session)
            await project.reload(session=session)
            return project
        except Exception as e:
            self._logger.error(f"Error updating project {project_id}: {e}")
            return None

    async def delete(self, project_id: str, session=None) -> bool:
        """Delete a project."""
        try:
            try:
                project = await Project.get(project_id, session=session)
            except Exception as e_get:
                self._logger.warning(
                    f"Project.get failed for delete id {project_id}: {e_get}. Trying fallback find_one by _id."
                )
                project = await Project.find_one({"_id": project_id})

            if not project:
                return False

            await project.delete(session=session)
            return True
        except Exception as e:
            self._logger.error(f"Error deleting project {project_id}: {e}")
            return False
