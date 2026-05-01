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
from projects_service.data.project_repository import ProjectRepository
from projects_service.data.task_repository import TaskRepository
from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.services.project_service import ProjectService
from projects_service.services.task_service import TaskService
from projects_service.services.context_tree_service import ContextTreeService
from projects_service.api.v1.projects import router as projects_router
from projects_service.api.v1.tasks import router as tasks_router
from projects_service.api.v1.context_tree import router as context_tree_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting up application...")

    # MongoDB connection
    client = AsyncIOMotorClient(settings.mongodb_url)
    database = client[settings.database_name]

    # Initialize Beanie with the document models
    await init_beanie(database, document_models=[Project, Task, ContextTreeNode])

    # Create repositories
    project_repository = ProjectRepository(client)
    app.state.project_repository = project_repository

    task_repository = TaskRepository(client)
    app.state.task_repository = task_repository

    context_tree_repository = ContextTreeRepository(client)
    app.state.context_tree_repository = context_tree_repository

    # Create services
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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(context_tree_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
