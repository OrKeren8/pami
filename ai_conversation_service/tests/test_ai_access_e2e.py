"""The AI service must not serve a project the caller cannot see.

Every endpoint here used to take a project_id, or a conversation_id resolving to one, straight
from the client - so naming someone else's project was enough to read their transcripts and
search their vectors. This is the highest-severity failure mode in the whole feature: the
product is a store of what the user has said.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_conversation_service.api.v1.ai_conversations import (
    router as ai_conversations_router,
)
from ai_conversation_service.core.config import settings
from ai_conversation_service.dependencies import get_ai_conversation_service
from ai_conversation_service.models.ai_conversation import Conversation

MINE = "project-mine"
THEIRS = "project-theirs"


class MembershipStub:
    """Stands in for projects-service, which owns membership."""

    def __init__(self, allowed: set[str], fail: bool = False):
        self.allowed = allowed
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def can_access_project(self, user_id: str, project_id: str) -> bool:
        self.calls.append((user_id, project_id))
        if self.fail:
            # Stands in for projects-service being unreachable.
            return False
        return project_id in self.allowed


class StubService:
    def __init__(self, membership: MembershipStub):
        self.projects_service_client = membership
        self.chunk_index_service = None
        self.context_retrieval_service = None
        self.conversations: dict[str, Conversation] = {}

    def add_conversation(self, project_id: str) -> str:
        conversation = Conversation(str(uuid4()), "node-1", project_id)
        self.conversations[conversation.conversation_id] = conversation
        return conversation.conversation_id

    async def get_conversation(self, conversation_id: str):
        return self.conversations.get(conversation_id)

    async def get_conversation_history(self, conversation_id: str, limit=None):
        conversation = self.conversations.get(conversation_id)
        return conversation.to_dict() if conversation else None

    async def create_conversation(self, context_node_id, project_id, title=None):
        conversation = Conversation(str(uuid4()), context_node_id, project_id)
        self.conversations[conversation.conversation_id] = conversation
        return conversation

    async def list_conversations_for_project(self, project_id: str):
        return [
            conversation.to_dict()
            for conversation in self.conversations.values()
            if conversation.project_id == project_id
        ]

    async def list_conversations_for_node(self, node_id: str):
        return [conversation.to_dict() for conversation in self.conversations.values()]

    async def purge_conversation(self, conversation_id: str):
        return self.conversations.pop(conversation_id, None) is not None


def _client(allowed=frozenset({MINE}), fail=False):
    membership = MembershipStub(set(allowed), fail=fail)
    service = StubService(membership)

    app = FastAPI()
    app.include_router(ai_conversations_router, prefix="/ai")
    app.dependency_overrides[get_ai_conversation_service] = lambda: service
    app.state.ai_conversation_service = service

    return TestClient(app), service, membership


def test_listing_another_users_project_is_refused():
    client, service, _ = _client()
    service.add_conversation(THEIRS)

    response = client.get(f"/ai/ai-conversations/project/{THEIRS}")

    assert response.status_code == 404


def test_listing_my_own_project_still_works():
    client, service, _ = _client()
    service.add_conversation(MINE)

    response = client.get(f"/ai/ai-conversations/project/{MINE}")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_reading_a_conversation_in_another_users_project_is_refused():
    client, service, _ = _client()
    conversation_id = service.add_conversation(THEIRS)

    assert client.get(f"/ai/ai-conversations/{conversation_id}").status_code == 404


def test_sending_a_message_into_another_users_conversation_is_refused():
    client, service, _ = _client()
    conversation_id = service.add_conversation(THEIRS)

    response = client.post(
        f"/ai/ai-conversations/{conversation_id}/messages", json={"message": "hello"}
    )

    assert response.status_code == 404


def test_deleting_another_users_conversation_is_refused():
    client, service, _ = _client()
    conversation_id = service.add_conversation(THEIRS)

    assert client.delete(f"/ai/ai-conversations/{conversation_id}").status_code == 404
    assert conversation_id in service.conversations, "it must still be there"


def test_creating_a_conversation_in_another_users_project_is_refused():
    client, _, _ = _client()

    response = client.post(
        "/ai/ai-conversations/",
        json={"context_node_id": "node-1", "project_id": THEIRS},
    )

    assert response.status_code == 404


def test_node_listing_filters_by_project_membership():
    """A node id says nothing about who may see it, so each row is filtered."""
    client, service, _ = _client()
    service.add_conversation(MINE)
    service.add_conversation(THEIRS)

    response = client.get("/ai/ai-conversations/node/node-1")

    assert response.status_code == 200
    assert [row["project_id"] for row in response.json()] == [MINE]


def test_access_check_failure_denies_rather_than_allows():
    """If membership cannot be established, refuse.

    An outage that turned into "everyone can read everything" would be far worse than an
    outage that refuses.
    """
    client, service, _ = _client(fail=True)
    service.add_conversation(MINE)

    assert client.get(f"/ai/ai-conversations/project/{MINE}").status_code == 404


@pytest.mark.parametrize("project_id", [MINE, THEIRS])
def test_every_project_scoped_request_asks_projects_service(project_id):
    """The check must actually be reached, not skipped by a code path."""
    client, service, membership = _client()
    service.add_conversation(project_id)

    client.get(f"/ai/ai-conversations/project/{project_id}")

    assert membership.calls, "no membership check was performed at all"


def test_a_peer_service_with_the_right_key_may_purge_any_conversation(monkeypatch):
    """projects-service deletes a node's conversation from a background task.

    There is no user token to forward - the work happens after the request that triggered it -
    and projects-service has already checked the caller owns the project. Without this, turning
    on the service key would make every node deletion fail: the purge would 401, and the node
    is deliberately kept when its conversation survives.
    """
    monkeypatch.setattr(settings, "service_key", "s3cret", raising=False)
    client, service, _ = _client()
    conversation_id = service.add_conversation(THEIRS)

    response = client.delete(
        f"/ai/ai-conversations/{conversation_id}", headers={"X-Service-Key": "s3cret"}
    )

    assert response.status_code == 200
    assert conversation_id not in service.conversations


def test_a_wrong_service_key_is_not_a_way_in(monkeypatch):
    """The key must be compared, not merely present."""
    monkeypatch.setattr(settings, "service_key", "s3cret", raising=False)
    client, service, _ = _client()
    conversation_id = service.add_conversation(THEIRS)

    response = client.delete(
        f"/ai/ai-conversations/{conversation_id}", headers={"X-Service-Key": "guess"}
    )

    assert response.status_code == 404, "a bad key must fall back to the user check"
    assert conversation_id in service.conversations


def test_a_service_key_header_means_nothing_when_none_is_configured(monkeypatch):
    """Otherwise sending the header would be a bypass before the key is distributed."""
    monkeypatch.setattr(settings, "service_key", "", raising=False)
    client, service, _ = _client()
    conversation_id = service.add_conversation(THEIRS)

    response = client.delete(
        f"/ai/ai-conversations/{conversation_id}", headers={"X-Service-Key": "anything"}
    )

    assert response.status_code == 404
