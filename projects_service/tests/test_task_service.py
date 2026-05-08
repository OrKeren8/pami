import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from projects_service.models.task import Task
from projects_service.services.task_service import TaskService
from projects_service.schemas.task_schemas import (
    CreateTaskRequest,
    UpdateTaskRequest,
    TaskResponse,
)
from projects_service.data.task_repository import TaskRepository


class TestTaskService:
    @pytest.fixture
    def mock_repository(self):
        return MagicMock(spec=TaskRepository)

    @pytest.fixture
    def service(self, mock_repository):
        return TaskService(mock_repository)

    @pytest.mark.asyncio
    @patch("projects_service.services.task_service.Task")
    async def test_create_task(self, mock_task_class, service, mock_repository):
        """Test creating a task."""
        project_id = "507f1f77bcf86cd799439011"
        request = CreateTaskRequest(
            title="Test Task",
            description="Test description",
            status="todo",
            assignee="user@example.com",
            dependencies=["task-1", "task-2"],
        )

        # Mock the task instance
        mock_task_instance = MagicMock()
        mock_task_class.return_value = mock_task_instance

        # Mock the created task from repository
        created_task = MagicMock()
        created_task.id = "507f1f77bcf86cd799439012"
        created_task.title = "Test Task"
        created_task.description = "Test description"
        created_task.status = "todo"
        created_task.assignee = "user@example.com"
        created_task.dependencies = ["task-1", "task-2"]
        created_task.project_id = project_id
        created_task.due_date = None
        created_task.created_at = datetime.utcnow()
        created_task.updated_at = datetime.utcnow()

        mock_repository.create = AsyncMock(return_value=created_task)

        result = await service.create_task(project_id, request)

        assert isinstance(result, TaskResponse)
        assert result.id == "507f1f77bcf86cd799439012"
        assert result.title == "Test Task"
        assert result.description == "Test description"
        assert result.status == "todo"
        assert result.assignee == "user@example.com"
        assert result.dependencies == ["task-1", "task-2"]
        assert result.project_id == project_id

        # Verify repository was called
        mock_repository.create.assert_called_once()
        mock_task_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_found(self, service, mock_repository):
        """Test getting a task when found."""
        task_id = "507f1f77bcf86cd799439012"

        task = MagicMock()
        task.id = task_id
        task.title = "Test Task"
        task.description = "Test description"
        task.status = "todo"
        task.assignee = "user@example.com"
        task.dependencies = []
        task.project_id = "507f1f77bcf86cd799439011"
        task.due_date = None
        task.created_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()

        mock_repository.get_by_id = AsyncMock(return_value=task)

        result = await service.get_task(task_id)

        assert result is not None
        assert result.id == task_id
        assert result.title == "Test Task"
        assert result.assignee == "user@example.com"
        mock_repository.get_by_id.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, service, mock_repository):
        """Test getting a task when not found."""
        task_id = "507f1f77bcf86cd799439012"

        mock_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.get_task(task_id)

        assert result is None
        mock_repository.get_by_id.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_list_tasks_by_project(self, service, mock_repository):
        """Test listing tasks by project."""
        project_id = "507f1f77bcf86cd799439011"
        task1 = MagicMock()
        task1.id = "507f1f77bcf86cd799439012"
        task1.title = "Task 1"
        task1.status = "todo"
        task1.project_id = project_id
        task1.assignee = "user1@example.com"
        task1.description = None
        task1.due_date = None
        task1.dependencies = []
        task1.created_at = datetime.utcnow()
        task1.updated_at = datetime.utcnow()

        task2 = MagicMock()
        task2.id = "507f1f77bcf86cd799439013"
        task2.title = "Task 2"
        task2.status = "done"
        task2.project_id = project_id
        task2.assignee = "user2@example.com"
        task2.description = None
        task2.due_date = None
        task2.dependencies = []
        task2.created_at = datetime.utcnow()
        task2.updated_at = datetime.utcnow()

        tasks = [task1, task2]

        mock_repository.list_by_project = AsyncMock(return_value=tasks)

        result = await service.list_tasks_by_project(project_id)

        assert len(result) == 2
        assert result[0].title == "Task 1"
        assert result[1].title == "Task 2"
        assert all(isinstance(r, TaskResponse) for r in result)
        assert all(r.project_id == project_id for r in result)
        mock_repository.list_by_project.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_update_task_found(self, service, mock_repository):
        """Test updating a task when found."""
        task_id = "507f1f77bcf86cd799439012"
        request = UpdateTaskRequest(
            status="in-progress", assignee="newuser@example.com"
        )

        updated_task = MagicMock()
        updated_task.id = task_id
        updated_task.title = "Test Task"
        updated_task.description = "Test description"
        updated_task.status = "in-progress"
        updated_task.assignee = "newuser@example.com"
        updated_task.dependencies = []
        updated_task.project_id = "507f1f77bcf86cd799439011"
        updated_task.due_date = None
        updated_task.created_at = datetime.utcnow()
        updated_task.updated_at = datetime.utcnow()

        mock_repository.update = AsyncMock(return_value=updated_task)

        result = await service.update_task(task_id, request)

        assert result is not None
        assert result.status == "in-progress"
        assert result.assignee == "newuser@example.com"
        mock_repository.update.assert_called_once()
        call_args = mock_repository.update.call_args[0]
        assert call_args[0] == task_id
        assert "status" in call_args[1]
        assert "assignee" in call_args[1]
        assert "updated_at" in call_args[1]
        assert call_args[1]["status"] == "in-progress"
        assert call_args[1]["assignee"] == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, service, mock_repository):
        """Test updating a task when not found."""
        task_id = "507f1f77bcf86cd799439012"
        request = UpdateTaskRequest(status="in-progress")

        mock_repository.update = AsyncMock(return_value=None)

        result = await service.update_task(task_id, request)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_task_found(self, service, mock_repository):
        """Test deleting a task when found."""
        task_id = "507f1f77bcf86cd799439012"

        mock_repository.delete = AsyncMock(return_value=True)

        result = await service.delete_task(task_id)

        assert result is True
        mock_repository.delete.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, service, mock_repository):
        """Test deleting a task when not found."""
        task_id = "507f1f77bcf86cd799439012"

        mock_repository.delete = AsyncMock(return_value=False)

        result = await service.delete_task(task_id)

        assert result is False
        mock_repository.delete.assert_called_once_with(task_id)
