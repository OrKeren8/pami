"""Organizing a node: what the graph ends up labelled with.

Topics are the only part of a node the UI can group by, so a topic that describes the
conversation instead of its subject is worse than no topic at all - it groups everything and
filters nothing. This drives the real route with a stubbed model and asserts on what comes out
the other side.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_conversation_service.api.v1.tree_analysis import router as tree_analysis_router
from ai_conversation_service.core.auth import require_service_key
from ai_conversation_service.dependencies import get_tree_analysis_service
from ai_conversation_service.services.tree_analysis_service import TreeAnalysisService

TRANSCRIPT = [
    {"role": "user", "content": "Hello! Can you help me with the load balancer?"},
    {
        "role": "assistant",
        "content": "The ALB covers two availability zones while the service launches tasks "
        "in six, so the target group ends up empty.",
    },
]


class StubConversation:
    def __init__(self):
        self.conversation_id = "conv-1"
        self.project_id = "project-1"
        self.title = "Load balancer"
        # The service reads messages as dicts, not objects: it builds the prompt with
        # msg["role"] and msg["content"].
        self.messages = list(TRANSCRIPT)

    def to_dict(self):
        return {
            "conversation_id": self.conversation_id,
            "project_id": self.project_id,
            "messages": TRANSCRIPT,
        }


class StubConversationService:
    async def get_conversation(self, conversation_id: str):
        return StubConversation() if conversation_id == "conv-1" else None


class StubMessage:
    def __init__(self, content):
        self.content = content


class StubChoice:
    def __init__(self, content):
        self.message = StubMessage(content)


class StubResponse:
    def __init__(self, content):
        self.choices = [StubChoice(content)]


class StubCompletions:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return StubResponse(json.dumps(self.payload))


class StubOpenAI:
    """Stands in for the model, and keeps the prompt so the test can read what it was told."""

    def __init__(self, payload):
        self.chat = type("Chat", (), {"completions": StubCompletions(payload)})()

    @property
    def prompts(self) -> list[dict]:
        return self.chat.completions.calls


def organize(payload) -> tuple[dict, StubOpenAI]:
    """Run the real route against a stubbed model, and hand back what it answered."""
    client = StubOpenAI(payload)
    # No chunk index: sibling scoring is embeddings work with its own tests, and passing None
    # is the service's own documented "cannot score" path.
    service = TreeAnalysisService(
        ai_conversation_service=StubConversationService(),
        openai_client=client,
        chunk_index_service=None,
    )

    app = FastAPI()
    app.include_router(tree_analysis_router)
    app.dependency_overrides[get_tree_analysis_service] = lambda: service
    app.dependency_overrides[require_service_key] = lambda: "projects-service"

    response = TestClient(app).post(
        "/tree-analysis/organize-node",
        json={"node_id": "node-1", "conversation_id": "conv-1", "current_tree": []},
    )
    assert response.status_code == 200, response.text
    return response.json(), client


BASE = {
    "header": "ECS ALB Subnet Alignment",
    "summary": "The load balancer covered two zones while the service used six, so the "
    "target group stayed empty.",
    "reasoning": "Networking problem.",
}


def test_topics_about_the_medium_are_dropped():
    """ "greeting" and "assistant response" are true of every conversation ever held."""
    organized, _ = organize(
        {
            **BASE,
            "topics": [
                "greeting",
                "assistant response",
                "user interaction",
                "load balancer",
                "networking",
            ],
        }
    )

    assert organized["topics"] == ["load balancer", "networking"]


def test_a_subject_word_keeps_the_topic():
    """The test is per word, not per phrase: "user accounts" is a subject, "user" is not."""
    organized, _ = organize(
        {**BASE, "topics": ["user accounts", "response caching", "user"]}
    )

    assert organized["topics"] == ["user accounts", "response caching"]


def test_nothing_but_medium_topics_is_kept_rather_than_emptied():
    """A thin conversation still gets a header and a summary.

    Dropping every topic would either fail the organization pass or leave the node with no
    tags at all, and the tags are the least valuable part of what this pass produces.
    """
    organized, _ = organize({**BASE, "topics": ["greeting", "small talk"]})

    assert organized["topics"] == ["greeting", "small talk"]


def test_topics_are_lowercased_and_deduplicated():
    organized, _ = organize(
        {**BASE, "topics": ["Networking", "networking", " Load Balancer "]}
    )

    assert organized["topics"] == ["networking", "load balancer"]


def test_the_model_is_told_not_to_tag_the_medium():
    """The filter is the guarantee, but the prompt is what makes it rarely necessary."""
    _, client = organize({**BASE, "topics": ["networking"]})

    system_prompt = client.prompts[0]["messages"][0]["content"]
    assert "Topic rules:" in system_prompt
    assert "greeting" in system_prompt, (
        "the prompt must name the medium words it does not want, not merely ask for good ones"
    )


def test_an_unknown_conversation_is_a_404():
    client = StubOpenAI({**BASE, "topics": ["networking"]})
    service = TreeAnalysisService(
        ai_conversation_service=StubConversationService(),
        openai_client=client,
        chunk_index_service=None,
    )

    app = FastAPI()
    app.include_router(tree_analysis_router)
    app.dependency_overrides[get_tree_analysis_service] = lambda: service
    app.dependency_overrides[require_service_key] = lambda: "projects-service"

    response = TestClient(app).post(
        "/tree-analysis/organize-node",
        json={"node_id": "node-1", "conversation_id": "missing", "current_tree": []},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("header", ["Overview", "A Much Too Long Header For The Rules"])
def test_a_header_outside_three_to_five_words_is_refused(header):
    """The organizer's own rule, exercised through the route rather than trusted."""
    client = StubOpenAI({**BASE, "header": header, "topics": ["networking"]})
    service = TreeAnalysisService(
        ai_conversation_service=StubConversationService(),
        openai_client=client,
        chunk_index_service=None,
    )

    app = FastAPI()
    app.include_router(tree_analysis_router)
    app.dependency_overrides[get_tree_analysis_service] = lambda: service
    app.dependency_overrides[require_service_key] = lambda: "projects-service"

    response = TestClient(app).post(
        "/tree-analysis/organize-node",
        json={"node_id": "node-1", "conversation_id": "conv-1", "current_tree": []},
    )

    # 502, not 404: the conversation exists, the model's answer is what is unusable.
    assert response.status_code == 502, (
        "a header that breaks the rule must not be stored"
    )
