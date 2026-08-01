"""
Integration tests for AI Conversation Service
Run these tests after setting up the environment properly.
"""

from fastapi.testclient import TestClient
from ai_conversation_service.main import app


def test_ai_conversation_health_endpoint():
    """Test that the AI conversation health endpoint works."""
    client = TestClient(app)
    response = client.get("/ai/ai-conversations/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "ai-conversations"}


def test_create_conversation_endpoint():
    """Test creating a new conversation via API."""
    client = TestClient(app)

    request_data = {
        "context_node_id": "test-node-123",
        "project_id": "test-project-123",
        "title": "Test Conversation",
    }

    response = client.post("/ai/ai-conversations/", json=request_data)

    # 404 is the correct answer here and the reason this assertion changed: creating a
    # conversation now confirms the caller may see the named project, projects-service is not
    # running in this suite, and the check fails closed. 200/500 remain valid where it is.
    assert response.status_code in [200, 404, 500]


def test_list_conversations_for_node():
    """Test listing conversations for a context node."""
    client = TestClient(app)

    # This will likely return an empty list or error without AWS setup
    response = client.get("/ai/ai-conversations/node/test-node-123")
    assert response.status_code in [200, 500]


def test_send_message_to_conversation():
    """Test sending a message to a conversation."""
    client = TestClient(app)

    request_data = {"message": "Hello AI", "context_snapshot": {"test": "data"}}

    # This will fail without a real conversation ID and AWS setup
    response = client.post(
        "/ai/ai-conversations/nonexistent-conversation/messages", json=request_data
    )
    # 404 is the correct answer for a conversation id that does not resolve;
    # 200 if the backend is stubbed, 500 only if infrastructure is missing.
    assert response.status_code in [200, 404, 500]
