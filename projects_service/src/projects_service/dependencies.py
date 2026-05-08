from functools import lru_cache
from fastapi import Request

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
