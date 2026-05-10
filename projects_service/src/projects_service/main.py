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
from projects_service.services.ai_conversation_service.service import AIConversationService
from projects_service.api.v1.ai_conversations import router as ai_conversations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting up application...")

    # Initialize Beanie with connection string
    await init_beanie(
        connection_string=settings.mongodb_url,
        document_models=[Project, Task, ContextTreeNode],
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
    project_service = ProjectService(project_repository)
    app.state.project_service = project_service

    task_service = TaskService(task_repository)
    app.state.task_service = task_service

    context_tree_service = ContextTreeService(context_tree_repository)
    app.state.context_tree_service = context_tree_service

    # Initialize AI conversation service
    ai_conversation_service = AIConversationService()
    app.state.ai_conversation_service = ai_conversation_service

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
app.include_router(ai_conversations_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
