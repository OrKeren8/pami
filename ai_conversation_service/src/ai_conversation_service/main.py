from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from ai_conversation_service.core.config import settings
from ai_conversation_service.services.ai_conversation_service.service import (
    AIConversationService,
)
from ai_conversation_service.services.tree_analysis_service import TreeAnalysisService
from ai_conversation_service.api.v1.ai_conversations import (
    router as ai_conversations_router,
)
from ai_conversation_service.api.v1.tree_analysis import (
    router as tree_analysis_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting up AI Conversation Service...")

    # Initialize AI conversation service
    ai_conversation_service = AIConversationService()
    app.state.ai_conversation_service = ai_conversation_service

    # Initialize tree analysis service
    tree_analysis_service = TreeAnalysisService(
        ai_conversation_service,
        ai_conversation_service.openai_client,
    )
    app.state.tree_analysis_service = tree_analysis_service

    logger.info("AI Conversation Service initialized")

    yield

    logger.info("AI Conversation Service shutting down")


app = FastAPI(
    title="PAMI AI Conversation Service",
    description="Microservice for AI-powered conversations with OpenAI and S3 storage",
    version="0.1.0",
    lifespan=lifespan,
    root_path="/ai",
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
app.include_router(ai_conversations_router)
app.include_router(tree_analysis_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-conversation-service",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
