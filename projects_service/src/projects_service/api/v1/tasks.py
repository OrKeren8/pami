from fastapi import APIRouter, Depends, HTTPException
from typing import List
from projects_service.schemas.task_schemas import (
    CreateTaskRequest,
    UpdateTaskRequest,
    TaskResponse,
)
from projects_service.services.task_service import TaskService
from projects_service.dependencies import get_task_service
from projects_service.core.access import ProjectForMemberDep, TaskForMemberDep

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse)
async def create_task(
    request: CreateTaskRequest,
    project: ProjectForMemberDep,
    service: TaskService = Depends(get_task_service),
):
    return await service.create_task(str(project.id), request)


@router.get("/projects/{project_id}/tasks", response_model=List[TaskResponse])
async def list_tasks(
    project: ProjectForMemberDep,
    service: TaskService = Depends(get_task_service),
):
    return await service.list_tasks_by_project(str(project.id))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task: TaskForMemberDep,
    service: TaskService = Depends(get_task_service),
):
    found = await service.get_task(str(task.id))
    if not found:
        raise HTTPException(status_code=404, detail="Task not found")
    return found


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    request: UpdateTaskRequest,
    task: TaskForMemberDep,
    service: TaskService = Depends(get_task_service),
):
    updated = await service.update_task(str(task.id), request)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.delete("/{task_id}")
async def delete_task(
    task: TaskForMemberDep,
    service: TaskService = Depends(get_task_service),
):
    deleted = await service.delete_task(str(task.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}
