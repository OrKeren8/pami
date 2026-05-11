from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

from ai_conversation_service.models.ai_conversation import Conversation


class AIConversationRepository(ABC):
    """Abstract repository for AI conversation data operations."""

    @abstractmethod
    async def save_conversation(self, conversation: Conversation) -> None:
        """Save a conversation."""
        pass

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        pass

    @abstractmethod
    async def list_conversations_for_node(
        self, context_node_id: str
    ) -> List[Dict[str, Any]]:
        """List all conversations for a context node."""
        pass


class InMemoryAIConversationRepository(AIConversationRepository):
    """In-memory implementation of AI conversation repository."""

    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}

    async def save_conversation(self, conversation: Conversation) -> None:
        """Save a conversation to memory."""
        self._conversations[conversation.conversation_id] = conversation

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID from memory."""
        return self._conversations.get(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation from memory."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False

    async def list_conversations_for_node(
        self, context_node_id: str
    ) -> List[Dict[str, Any]]:
        """List all conversations for a context node."""
        conversations = []
        for conv in self._conversations.values():
            if conv.context_node_id == context_node_id:
                conversations.append(
                    {
                        "conversation_id": conv.conversation_id,
                        "title": conv.title,
                        "created_at": conv.created_at,
                        "updated_at": conv.updated_at,
                        "message_count": len(conv.messages),
                        "status": conv.status,
                    }
                )
        return conversations
