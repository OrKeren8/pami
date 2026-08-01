from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from projects_service.core.config import settings
from projects_service.services.project_service import ProjectService
from projects_service.services.task_service import TaskService
from projects_service.services.context_tree_service import ContextTreeService


@lru_cache()
def get_config():
    """Get cached configuration instance."""
    return settings()


def get_project_service(request: Request) -> ProjectService:
    """Get project service from app state."""
    return request.app.state.project_service


def get_task_service(request: Request) -> TaskService:
    """Get task service from app state."""
    return request.app.state.task_service


def get_context_tree_service(request: Request) -> ContextTreeService:
    """Get context tree service from app state."""
    return request.app.state.context_tree_service


def get_project_repository(request: Request):
    """The project repository, for the access checks that must read membership."""
    return request.app.state.project_repository


def get_context_tree_repository(request: Request):
    """The node repository, for resolving a node to the project that owns it."""
    return request.app.state.context_tree_repository


def get_task_repository(request: Request):
    """The task repository, for resolving a task to the project that owns it."""
    return request.app.state.task_repository


def get_user_directory(request: Request):
    """The local user mirror, for resolving an invited email to an account."""
    return request.app.state.user_directory


ContextTreeServiceDep = Annotated[ContextTreeService, Depends(get_context_tree_service)]
