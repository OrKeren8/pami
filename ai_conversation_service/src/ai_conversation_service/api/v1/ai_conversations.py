from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from ai_conversation_service.schemas.ai_conversation_schemas import (
    CreateConversationRequest,
    SendMessageRequest,
    ConversationResponse,
    ConversationHistoryResponse,
    MessageResponse,
)
from ai_conversation_service.dependencies import get_ai_conversation_service
from ai_conversation_service.services.ai_conversation_service.service import (
    AIConversationService,
)

router = APIRouter(prefix="/ai-conversations", tags=["ai-conversations"])


@router.get("/health")
async def health_check():
    """Health check for AI conversation service."""
    return {"status": "healthy", "service": "ai-conversations"}


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    """Create a new AI conversation for a context node."""
    try:
        conversation = await service.create_conversation(
            request.context_node_id, request.project_id, request.title
        )
        return ConversationResponse(**conversation.to_dict())
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create conversation: {str(e)}"
        )


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    """Send a message to an AI conversation and get response."""
    try:
        ai_response = await service.send_message(
            conversation_id, request.message, request.context_snapshot
        )
        return {"response": ai_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    conversation_id: str,
    limit: Optional[int] = None,
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    """Get conversation history."""
    try:
        conversation = await service.get_conversation_history(conversation_id, limit)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationHistoryResponse(**conversation)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversation: {str(e)}"
        )


@router.get("/node/{context_node_id}", response_model=List[ConversationResponse])
async def list_conversations_for_node(
    context_node_id: str,
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    """List all conversations for a context node."""
    try:
        conversations = await service.list_conversations_for_node(context_node_id)
        return [ConversationResponse(**conv) for conv in conversations]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list conversations: {str(e)}"
        )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    """Delete a conversation."""
    try:
        deleted = await service.delete_conversation(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete conversation: {str(e)}"
        )
