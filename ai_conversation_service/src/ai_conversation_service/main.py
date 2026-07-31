from contextlib import asynccontextmanager
from beanie import init_beanie
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pymongo import AsyncMongoClient

from ai_conversation_service.core.config import settings
from ai_conversation_service.data.vector_index import ensure_vector_index
from ai_conversation_service.models.conversation_chunk import ConversationChunk
from ai_conversation_service.models.conversation_index_state import (
    ConversationIndexState,
)
from ai_conversation_service.agents.conversation_agent import build_conversation_agent
from ai_conversation_service.services.chunk_index_service import ChunkIndexService
from ai_conversation_service.services.context_retrieval_service import (
    ContextRetrievalService,
)
from ai_conversation_service.services.embedder_factory import build_embedder
from ai_conversation_service.services.projects_service_client import (
    ProjectsServiceClient,
)
from ai_conversation_service.services.reindex_trigger import ReindexTrigger
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
    """Assemble services bottom-up; an unavailable embedder degrades retrieval."""
    logger.info("Setting up AI Conversation Service...")

    projects_service_client = ProjectsServiceClient(settings.projects_api_url)

    embedder = await build_embedder()

    mongo_client = AsyncMongoClient(settings.mongodb_url)
    database = mongo_client[settings.database_name]
    await init_beanie(
        database=database,
        document_models=[ConversationChunk, ConversationIndexState],
    )

    chunk_index_service = ChunkIndexService(embedder, database) if embedder else None
    context_retrieval_service = (
        ContextRetrievalService(embedder, chunk_index_service, projects_service_client)
        if embedder
        else None
    )
    reindex_trigger = (
        ReindexTrigger(chunk_index_service, projects_service_client)
        if embedder
        else None
    )

    ai_conversation_service = AIConversationService(
        projects_service_client=projects_service_client,
        chunk_index_service=chunk_index_service,
        context_retrieval_service=context_retrieval_service,
        reindex_trigger=reindex_trigger,
        conversation_agent=build_conversation_agent() if embedder else None,
    )
    tree_analysis_service = TreeAnalysisService(
        ai_conversation_service,
        ai_conversation_service.openai_client,
        chunk_index_service,
    )

    app.state.embedder = embedder
    app.state.mongo_client = mongo_client
    app.state.chunk_index_service = chunk_index_service
    app.state.context_retrieval_service = context_retrieval_service
    app.state.reindex_trigger = reindex_trigger
    app.state.ai_conversation_service = ai_conversation_service
    app.state.tree_analysis_service = tree_analysis_service
    app.state.vector_index_ready = (
        await ensure_vector_index(database, embedder.dimensions) if embedder else False
    )

    if embedder:
        logger.info("Cross-conversation retrieval enabled")
    logger.info("AI Conversation Service initialized")

    yield

    await mongo_client.close()
    logger.info("AI Conversation Service shutting down")


app = FastAPI(
    title="PAMI AI Conversation Service",
    description="Microservice for AI-powered conversations with OpenAI and S3 storage",
    version="0.1.0",
    lifespan=lifespan,
)

# Only set a non-empty root_path when explicitly configured. Leaving it unset
# avoids routing mismatches in tests that call routes without a prefix.
if settings.api_root:
    app.root_path = settings.api_root

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers under the `/ai` prefix so ALB path-based routing (/ai/*)
# correctly forwards requests to the AI service endpoints. This ensures that
# requests arriving as `/ai/ai-conversations/...` or `/ai/tree-analysis/...`
# are matched by the internal routers.
app.include_router(ai_conversations_router, prefix="/ai")
app.include_router(tree_analysis_router, prefix="/ai")


# Both paths: the ALB forwards /ai/* here without stripping the prefix, so a bare /health is
# only reachable from inside the VPC (which is how the target-group check sees it) while
# anything outside — a deploy smoke check, a monitor — can only reach /ai/health.
@app.get("/ai/health")
@app.get("/health")
async def health_check():
    embedder = getattr(app.state, "embedder", None)
    retrieval_ready = bool(embedder) and bool(
        getattr(app.state, "vector_index_ready", False)
    )
    return {
        "status": "healthy",
        "service": "ai-conversation-service",
        "version": "0.1.0",
        "retrieval": "ready" if retrieval_ready else "degraded",
        "embedder": embedder.model_id if embedder else None,
    }


@app.get("/")
async def root_check():
    # Provide a simple root health response to satisfy ALB health checks
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
