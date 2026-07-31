import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from projects_service.services.project_service import ProjectService
from projects_service.schemas.project_schemas import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
    ProjectStatus,
)
from projects_service.data.project_repository import ProjectRepository


class TestProjectService:
    @pytest.fixture
    def mock_repository(self):
        return MagicMock(spec=ProjectRepository)

    @pytest.fixture
    def service(self, mock_repository):
        return ProjectService(mock_repository)

    @pytest.mark.asyncio
    @patch("projects_service.services.project_service.Project")
    async def test_create_project(self, mock_project_class, service, mock_repository):
        """Test creating a project."""
        request = CreateProjectRequest(
            name="Test Project",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
        )

        # Mock the project instance
        mock_project_instance = MagicMock()
        mock_project_class.return_value = mock_project_instance

        # Mock the created project from repository
        created_project = MagicMock()
        created_project.id = "507f1f77bcf86cd799439011"
        created_project.name = "Test Project"
        created_project.goal = "Test goal"
        created_project.status = ProjectStatus.ACTIVE
        created_project.created_at = datetime.utcnow()
        created_project.updated_at = datetime.utcnow()

        mock_repository.create = AsyncMock(return_value=created_project)

        result = await service.create_project(request, "user-1", "owner@example.com")

        assert isinstance(result, ProjectResponse)
        assert result.id == "507f1f77bcf86cd799439011"
        assert result.name == "Test Project"
        assert result.goal == "Test goal"
        assert result.status == ProjectStatus.ACTIVE

        # Verify repository was called
        mock_repository.create.assert_called_once()
        mock_project_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_project_found(self, service, mock_repository):
        """Test getting a project when found."""
        project_id = "507f1f77bcf86cd799439011"

        project = MagicMock()
        project.id = project_id
        project.name = "Test Project"
        project.goal = "Test goal"
        project.status = ProjectStatus.ACTIVE
        project.created_at = datetime.utcnow()
        project.updated_at = datetime.utcnow()

        mock_repository.get_by_id = AsyncMock(return_value=project)

        result = await service.get_project(project_id)

        assert result is not None
        assert result.id == project_id
        assert result.name == "Test Project"
        mock_repository.get_by_id.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, service, mock_repository):
        """Test getting a project when not found."""
        project_id = "507f1f77bcf86cd799439011"

        mock_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.get_project(project_id)

        assert result is None
        mock_repository.get_by_id.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_list_projects(self, service, mock_repository):
        """Only the caller's own projects: this used to list the whole database."""
        project1 = MagicMock()
        project1.name = "Project 1"
        project1.goal = "Goal 1"
        project1.status = ProjectStatus.ACTIVE
        project1.created_at = datetime.utcnow()
        project1.updated_at = datetime.utcnow()

        project2 = MagicMock()
        project2.name = "Project 2"
        project2.goal = "Goal 2"
        project2.status = ProjectStatus.COMPLETED
        project2.created_at = datetime.utcnow()
        project2.updated_at = datetime.utcnow()

        projects = [project1, project2]

        mock_repository.list_for_member = AsyncMock(return_value=projects)

        result = await service.list_projects("user-1")

        assert len(result) == 2
        assert result[0].name == "Project 1"
        assert result[1].name == "Project 2"
        assert all(isinstance(r, ProjectResponse) for r in result)
        mock_repository.list_for_member.assert_called_once_with("user-1")

    @pytest.mark.asyncio
    async def test_update_project_found(self, service, mock_repository):
        """Test updating a project when found."""
        project_id = "507f1f77bcf86cd799439011"
        request = UpdateProjectRequest(status=ProjectStatus.COMPLETED)

        updated_project = MagicMock()
        updated_project.id = project_id
        updated_project.name = "Test Project"
        updated_project.goal = "Test goal"
        updated_project.status = ProjectStatus.COMPLETED
        updated_project.created_at = datetime.utcnow()
        updated_project.updated_at = datetime.utcnow()

        mock_repository.update = AsyncMock(return_value=updated_project)

        result = await service.update_project(project_id, request)

        assert result is not None
        assert result.status == ProjectStatus.COMPLETED
        mock_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_project_not_found(self, service, mock_repository):
        """Test updating a project when not found."""
        project_id = "507f1f77bcf86cd799439011"
        request = UpdateProjectRequest(status=ProjectStatus.COMPLETED)

        mock_repository.update = AsyncMock(return_value=None)

        result = await service.update_project(project_id, request)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_project_found(self, service, mock_repository):
        """Test deleting a project when found."""
        project_id = "507f1f77bcf86cd799439011"

        mock_repository.delete = AsyncMock(return_value=True)

        result = await service.delete_project(project_id)

        assert result is True
        mock_repository.delete.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, service, mock_repository):
        """Test deleting a project when not found."""
        project_id = "507f1f77bcf86cd799439011"

        mock_repository.delete = AsyncMock(return_value=False)

        result = await service.delete_project(project_id)

        assert result is False
        mock_repository.delete.assert_called_once_with(project_id)
