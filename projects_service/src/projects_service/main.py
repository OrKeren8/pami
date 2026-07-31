from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from projects_service.core.config import settings
from projects_service.models.project import Project
from projects_service.models.task import Task
from projects_service.models.context_tree import ContextTreeNode
from projects_service.models.user import User
from projects_service.data.project_repository import ProjectRepository
from projects_service.data.task_repository import TaskRepository
from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.core.auth import prime_signing_keys
from projects_service.services.project_service import ProjectService
from projects_service.services.user_directory import UserDirectory
from projects_service.services.task_service import TaskService
from projects_service.services.context_tree_service import ContextTreeService
from projects_service.api.v1.projects import router as projects_router
from projects_service.api.v1.tasks import router as tasks_router
from projects_service.api.v1.context_tree import router as context_tree_router
from projects_service.api.v1.admin import router as admin_router
from projects_service.api.v1.session import router as session_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting up application...")

    mongodb_url_with_database = settings.mongodb_url

    if settings.database_name not in mongodb_url_with_database:
        mongodb_url_with_database = f"{settings.mongodb_url}/{settings.database_name}"

    # Initialize Beanie with connection string
    await init_beanie(
        connection_string=mongodb_url_with_database,
        document_models=[Project, Task, ContextTreeNode, User],
    )

    # Get database for repositories
    client = AsyncIOMotorClient(settings.mongodb_url)
    database = client[settings.database_name]
    # Create repositories
    project_repository = ProjectRepository(database)
    app.state.project_repository = project_repository

    task_repository = TaskRepository(database)
    app.state.task_repository = task_repository

    context_tree_repository = ContextTreeRepository(database)
    app.state.context_tree_repository = context_tree_repository

    # Create services
    app.state.user_directory = UserDirectory(project_repository)

    # Fetched now so the first authenticated request does not pay for the round trip. Warns
    # rather than raises: a container that never becomes healthy is rolled back, and an
    # unreachable Cognito must not fail a deploy of unrelated code.
    await prime_signing_keys()

    project_service = ProjectService(project_repository)
    app.state.project_service = project_service

    task_service = TaskService(task_repository)
    app.state.task_service = task_service

    context_tree_service = ContextTreeService(context_tree_repository)
    app.state.context_tree_service = context_tree_service

    logger.info("Database connected, repositories and services initialized")

    yield

    # Cleanup
    client.close()
    logger.info("Database connection closed")


app = FastAPI(
    title="PAMI Projects Service",
    description="Microservice for managing projects, tasks, and context trees in PAMI",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(context_tree_router)
app.include_router(session_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
