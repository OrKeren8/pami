from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class CreateConversationRequest(BaseModel):
    context_node_id: str
    project_id: str
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    message: str
    context_snapshot: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    context_snapshot: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None


class ConversationResponse(BaseModel):
    conversation_id: str
    context_node_id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    message_count: int
    # First thing the user asked. Titles are generated as "AI Discussion - <node id>", which
    # tells a reader looking for a past conversation nothing at all.
    preview: Optional[str] = None


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    context_node_id: str
    project_id: str
    title: str
    messages: List[MessageResponse]
    created_at: str
    updated_at: str
    status: str
