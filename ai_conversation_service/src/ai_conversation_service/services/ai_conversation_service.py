import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import os
from loguru import logger
from openai import AsyncOpenAI

from ai_conversation_service.core.config import settings


class ConversationMessage:
    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.utcnow().isoformat()


class Conversation:
    def __init__(self, conversation_id: str, context_node_id: str, project_id: str):
        self.conversation_id = conversation_id
        self.context_node_id = context_node_id
        self.project_id = project_id
        self.messages: List[Dict[str, Any]] = []
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.title = f"AI Discussion - {context_node_id}"
        self.status = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "context_node_id": self.context_node_id,
            "project_id": self.project_id,
            "title": self.title,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "message_count": len(self.messages),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        conv = cls(data["conversation_id"], data["context_node_id"], data["project_id"])
        conv.messages = data.get("messages", [])
        conv.created_at = data.get("created_at", conv.created_at)
        conv.updated_at = data.get("updated_at", conv.updated_at)
        conv.title = data.get("title", conv.title)
        conv.status = data.get("status", conv.status)
        return conv


class AIConversationService:
    """Service for managing AI conversations with OpenAI integration."""

    def __init__(self):
        self._logger = logger.bind(service="AIConversationService")

        # Initialize OpenAI client
        try:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self._logger.info("AI Conversation Service initialized successfully")
        except Exception as e:
            self._logger.error(f"Failed to initialize AI Conversation Service: {e}")
            self.openai_client = None

    async def create_conversation(
        self, context_node_id: str, project_id: str, title: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation for a context node."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")

        # Validate input parameters
        if not context_node_id or not project_id:
            raise ValueError("context_node_id and project_id are required")

        conversation_id = str(uuid.uuid4())
        conversation = Conversation(conversation_id, context_node_id, project_id)

        if title:
            # Sanitize title to prevent issues
            title = title.replace("/", "_").replace("\\", "_")[:100]  # Limit length
            conversation.title = title

        self._logger.info(
            f"Created conversation {conversation_id} for node {context_node_id}"
        )
        return conversation

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID (in-memory only for now)."""
        # For now, conversations are not persisted - this is a limitation
        # In a production system, you'd want to store conversations in a database
        self._logger.warning(
            "Conversation persistence not implemented - returning None"
        )
        return None

    async def send_message(
        self,
        conversation_id: str,
        user_message: str,
        context_snapshot: Optional[Dict] = None,
    ) -> str:
        """Send a message to the conversation and get AI response."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")

        # For now, we don't persist conversations, so we start fresh each time
        # In production, you'd load the conversation history from storage

        # Prepare messages for OpenAI
        messages = []

        # Add context if provided
        if context_snapshot:
            context_text = f"Context: {json.dumps(context_snapshot, indent=2)}"
            messages.append({"role": "system", "content": context_text})

        # Add user message
        messages.append({"role": "user", "content": user_message})

        # Get AI response
        ai_response = await self._call_openai(messages)

        self._logger.info(f"Processed message in conversation {conversation_id}")
        return ai_response

    async def get_conversation_history(
        self, conversation_id: str, limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get conversation history (not implemented for in-memory version)."""
        # For now, conversations are not persisted
        self._logger.warning(
            "Conversation history not available - persistence not implemented"
        )
        return None

    async def list_conversations_for_node(
        self, context_node_id: str
    ) -> List[Dict[str, Any]]:
        """List all conversations for a context node (not implemented for in-memory version)."""
        # For now, conversations are not persisted
        self._logger.warning(
            "Conversation listing not available - persistence not implemented"
        )
        return []

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation (not implemented for in-memory version)."""
        # For now, conversations are not persisted
        self._logger.warning(
            "Conversation deletion not available - persistence not implemented"
        )
        return True

    async def _call_openai(self, messages: List[Dict[str, Any]]) -> str:
        """Call OpenAI with conversation messages."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
            )

            ai_response = response.choices[0].message.content
            return ai_response

        except Exception as e:
            self._logger.error(f"OpenAI call failed: {e}")
            return "I apologize, but I'm having trouble responding right now. Please try again."

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters for English)."""
        return len(text) // 4
