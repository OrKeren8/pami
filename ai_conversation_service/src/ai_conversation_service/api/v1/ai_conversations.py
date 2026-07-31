from fastapi import APIRouter, HTTPException
from loguru import logger

from ai_conversation_service.schemas.ai_conversation_schemas import (
    CreateConversationRequest,
    SendMessageRequest,
    ConversationResponse,
    ConversationHistoryResponse,
)
from ai_conversation_service.core.config import settings
from ai_conversation_service.dependencies import AIConversationServiceDep
from ai_conversation_service.schemas.retrieval_schemas import (
    ContextHit,
    SearchContextRequest,
    SendMessageResult,
)
from ai_conversation_service.services.ai_conversation_service.service import (
    ConversationNotFoundError,
)

router = APIRouter(prefix="/ai-conversations", tags=["ai-conversations"])


@router.get("/health")
async def health_check():
    """Health check for AI conversation service."""
    return {"status": "healthy", "service": "ai-conversations"}


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    ai_conversation_service: AIConversationServiceDep,
):
    """Create a new AI conversation for a context node."""
    try:
        conversation = await ai_conversation_service.create_conversation(
            request.context_node_id, request.project_id, request.title
        )
        return ConversationResponse(**conversation.to_dict())
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create conversation: {str(e)}"
        )


@router.post("/{conversation_id}/messages", response_model=SendMessageResult)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    ai_conversation_service: AIConversationServiceDep,
):
    """Send a message and get a response, with any consulted conversations reported."""
    try:
        return await ai_conversation_service.send_message_with_context(
            conversation_id, request.message, request.context_snapshot
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        # Logged with the traceback: converting straight to a 500 left the service log
        # showing a bare status code with no reason, so a real failure could only be
        # diagnosed by reproducing it.
        logger.opt(exception=True).error(
            f"send_message failed for conversation {conversation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    conversation_id: str,
    ai_conversation_service: AIConversationServiceDep,
    limit: int | None = None,
):
    """Get conversation history."""
    try:
        conversation = await ai_conversation_service.get_conversation_history(
            conversation_id, limit
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationHistoryResponse(**conversation)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversation: {str(e)}"
        )


@router.get("/node/{context_node_id}", response_model=list[ConversationResponse])
async def list_conversations_for_node(
    context_node_id: str,
    ai_conversation_service: AIConversationServiceDep,
):
    """List all conversations for a context node."""
    try:
        conversations = await ai_conversation_service.list_conversations_for_node(
            context_node_id
        )
        return [ConversationResponse(**conv) for conv in conversations]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list conversations: {str(e)}"
        )


@router.post("/context-retrieval/search", response_model=list[ContextHit])
async def search_context(
    request: SearchContextRequest,
    ai_conversation_service: AIConversationServiceDep,
):
    """Run the same retrieval the agent tool runs. Debug only, disabled by default."""
    if not settings.enable_retrieval_debug_api:
        raise HTTPException(status_code=404, detail="Not found")
    if not ai_conversation_service.context_retrieval_service:
        raise HTTPException(status_code=503, detail="Retrieval is unavailable")
    return await ai_conversation_service.context_retrieval_service.search(
        project_id=request.project_id,
        query=request.query,
        exclude_conversation_id=request.exclude_conversation_id,
        limit=request.limit,
    )


@router.post("/context-retrieval/reindex/{conversation_id}", status_code=202)
async def reindex_conversation(
    conversation_id: str,
    ai_conversation_service: AIConversationServiceDep,
):
    """Force a reindex, ignoring the debounce. Idempotent."""
    if not ai_conversation_service.chunk_index_service:
        raise HTTPException(status_code=503, detail="Retrieval is unavailable")

    reindexed = await ai_conversation_service.force_reindex(conversation_id)
    if not reindexed:
        raise HTTPException(
            status_code=404, detail="Conversation not found or has no messages"
        )
    return {"status": "reindexed", "conversation_id": conversation_id}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    ai_conversation_service: AIConversationServiceDep,
):
    """Delete a conversation and remove it from the search index."""
    try:
        deleted = await ai_conversation_service.purge_conversation(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete conversation: {str(e)}"
        )
