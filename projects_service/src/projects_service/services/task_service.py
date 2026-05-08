from typing import List, Optional
from datetime import datetime
from loguru import logger

from projects_service.data.task_repository import TaskRepository
from projects_service.models.task import Task
from projects_service.schemas.task_schemas import (
    CreateTaskRequest,
    UpdateTaskRequest,
    TaskResponse,
)


class TaskService:
    """Service for task business logic."""

    def __init__(self, task_repository: TaskRepository):
        self._logger = logger.bind(service="TaskService")
        self._task_repository = task_repository

    async def create_task(
        self, project_id: str, request: CreateTaskRequest
    ) -> TaskResponse:
        """Create a new task."""
        # Create domain model from request
        task = Task(
            title=request.title,
            description=request.description,
            status=request.status,
            due_date=request.due_date,
            assignee=request.assignee,
            dependencies=request.dependencies,
            project_id=project_id,
        )
        created_task = await self._task_repository.create(task)

        return TaskResponse(
            id=str(created_task.id),
            title=created_task.title,
            description=created_task.description,
            status=created_task.status,
            due_date=created_task.due_date,
            assignee=created_task.assignee,
            dependencies=created_task.dependencies,
            project_id=created_task.project_id,
            created_at=created_task.created_at,
            updated_at=created_task.updated_at,
        )

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Get a task by ID."""
        task = await self._task_repository.get_by_id(task_id)
        if not task:
            return None

        return TaskResponse(
            id=str(task.id),
            title=task.title,
            description=task.description,
            status=task.status,
            due_date=task.due_date,
            assignee=task.assignee,
            dependencies=task.dependencies,
            project_id=task.project_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    async def list_tasks_by_project(self, project_id: str) -> List[TaskResponse]:
        """List all tasks for a project."""
        tasks = await self._task_repository.list_by_project(project_id)
        return [
            TaskResponse(
                id=str(t.id),
                title=t.title,
                description=t.description,
                status=t.status,
                due_date=t.due_date,
                assignee=t.assignee,
                dependencies=t.dependencies,
                project_id=t.project_id,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        ]

    async def update_task(
        self, task_id: str, request: UpdateTaskRequest
    ) -> Optional[TaskResponse]:
        """Update a task."""
        update_data = request.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        task = await self._task_repository.update(task_id, update_data)
        if not task:
            return None

        return TaskResponse(
            id=str(task.id),
            title=task.title,
            description=task.description,
            status=task.status,
            due_date=task.due_date,
            assignee=task.assignee,
            dependencies=task.dependencies,
            project_id=task.project_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        return await self._task_repository.delete(task_id)
