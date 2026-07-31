from typing import List, Optional
from datetime import datetime
from loguru import logger

from projects_service.data.project_repository import ProjectRepository
from projects_service.models.project import Project
from projects_service.schemas.project_schemas import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
)


class ProjectService:
    """Service for project business logic."""

    def __init__(self, project_repository: ProjectRepository):
        self._logger = logger.bind(service="ProjectService")
        self._project_repository = project_repository

    async def create_project(self, request: CreateProjectRequest) -> ProjectResponse:
        """Create a new project."""
        # Create domain model from request
        project = Project(
            name=request.name,
            goal=request.goal,
            status=request.status,
            color=request.color,
        )
        created_project = await self._project_repository.create(project)

        color_val = getattr(created_project, "color", None)
        color = color_val if isinstance(color_val, str) else None

        return ProjectResponse(
            id=str(created_project.id),
            name=created_project.name,
            goal=created_project.goal,
            status=created_project.status,
            color=color,
            created_at=created_project.created_at,
            updated_at=created_project.updated_at,
        )

    async def get_project(self, project_id: str) -> Optional[ProjectResponse]:
        """Get a project by ID."""
        project = await self._project_repository.get_by_id(project_id)
        if not project:
            return None

        color_val = getattr(project, "color", None)
        color = color_val if isinstance(color_val, str) else None

        return ProjectResponse(
            id=str(project.id),
            name=project.name,
            goal=project.goal,
            status=project.status,
            color=color,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def list_projects(self) -> List[ProjectResponse]:
        """List all projects."""
        projects = await self._project_repository.list_all()
        return [
            ProjectResponse(
                id=str(p.id),
                name=p.name,
                goal=p.goal,
                status=p.status,
                color=(
                    getattr(p, "color", None)
                    if isinstance(getattr(p, "color", None), str)
                    else None
                ),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in projects
        ]

    async def update_project(
        self, project_id: str, request: UpdateProjectRequest
    ) -> Optional[ProjectResponse]:
        """Update a project."""
        update_data = request.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        project = await self._project_repository.update(project_id, update_data)
        if not project:
            return None

        color_val = getattr(project, "color", None)
        return ProjectResponse(
            id=str(project.id),
            name=project.name,
            goal=project.goal,
            status=project.status,
            color=str(color_val) if color_val is not None else None,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        return await self._project_repository.delete(project_id)
