from typing import List, Optional, Dict, Any
from datetime import datetime


class ConversationMessage:
    """Model for conversation messages."""

    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.utcnow().isoformat()


class Conversation:
    """Model for AI conversations."""

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
