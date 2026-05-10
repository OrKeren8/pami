from fastapi import APIRouter, Depends, HTTPException
from typing import List
from projects_service.schemas.task_schemas import (
    CreateTaskRequest,
    UpdateTaskRequest,
    TaskResponse,
)
from projects_service.services.task_service import TaskService
from projects_service.dependencies import get_task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse)
async def create_task(
    project_id: str,
    request: CreateTaskRequest,
    service: TaskService = Depends(get_task_service),
):
    return await service.create_task(project_id, request)


@router.get("/projects/{project_id}/tasks", response_model=List[TaskResponse])
async def list_tasks(
    project_id: str,
    service: TaskService = Depends(get_task_service),
):
    return await service.list_tasks_by_project(project_id)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
):
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    service: TaskService = Depends(get_task_service),
):
    task = await service.update_task(task_id, request)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
):
    deleted = await service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}
