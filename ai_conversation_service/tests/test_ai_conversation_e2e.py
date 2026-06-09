from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_conversation_service.api.v1.ai_conversations import (
    router as ai_conversations_router,
)
from ai_conversation_service.dependencies import get_ai_conversation_service
from ai_conversation_service.models.ai_conversation import Conversation


class InMemoryAIConversationService:
    def __init__(self):
        self.conversations = {}

    async def create_conversation(
        self, context_node_id: str, project_id: str, title: str | None = None
    ):
        conversation = Conversation(str(uuid4()), context_node_id, project_id)
        if title:
            conversation.title = title
        self.conversations[conversation.conversation_id] = conversation
        return conversation

    async def send_message(
        self, conversation_id: str, user_message: str, context_snapshot=None
    ):
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            raise Exception("Conversation not found")

        conversation.messages.append(
            {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.utcnow().isoformat(),
                "context_snapshot": context_snapshot,
            }
        )
        ai_text = f"Echo: {user_message}"
        conversation.messages.append(
            {
                "role": "assistant",
                "content": ai_text,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        conversation.updated_at = datetime.utcnow().isoformat()
        return ai_text

    async def get_conversation_history(self, conversation_id: str, limit=None):
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return None
        messages = conversation.messages[-limit:] if limit else conversation.messages
        return {
            "conversation_id": conversation.conversation_id,
            "context_node_id": conversation.context_node_id,
            "project_id": conversation.project_id,
            "title": conversation.title,
            "messages": messages,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "status": conversation.status,
        }

    async def list_conversations_for_node(self, context_node_id: str):
        results = []
        for conv in self.conversations.values():
            if conv.context_node_id == context_node_id:
                results.append(conv.to_dict())
        return results

    async def delete_conversation(self, conversation_id: str):
        return self.conversations.pop(conversation_id, None) is not None


def _make_test_client():
    app = FastAPI()
    app.include_router(ai_conversations_router, prefix="/ai")

    fake_service = InMemoryAIConversationService()
    app.dependency_overrides[get_ai_conversation_service] = lambda: fake_service

    return TestClient(app)


def test_ai_conversation_end_to_end_flow():
    client = _make_test_client()

    created = client.post(
        "/ai/ai-conversations/",
        json={
            "context_node_id": "node-123",
            "project_id": "project-123",
            "title": "E2E Conversation",
        },
    )
    assert created.status_code == 200
    created_json = created.json()
    conversation_id = created_json["conversation_id"]
    assert created_json["message_count"] == 0

    sent = client.post(
        f"/ai/ai-conversations/{conversation_id}/messages",
        json={
            "message": "Hello from E2E",
            "context_snapshot": {"phase": "integration"},
        },
    )
    assert sent.status_code == 200
    assert sent.json()["response"] == "Echo: Hello from E2E"

    history = client.get(f"/ai/ai-conversations/{conversation_id}")
    assert history.status_code == 200
    history_json = history.json()
    assert len(history_json["messages"]) == 2
    assert history_json["messages"][0]["role"] == "user"
    assert history_json["messages"][1]["role"] == "assistant"

    listed = client.get("/ai/ai-conversations/node/node-123")
    assert listed.status_code == 200
    listed_json = listed.json()
    assert len(listed_json) == 1
    assert listed_json[0]["conversation_id"] == conversation_id

    deleted = client.delete(f"/ai/ai-conversations/{conversation_id}")
    assert deleted.status_code == 200

    missing = client.get(f"/ai/ai-conversations/{conversation_id}")
    assert missing.status_code == 404
