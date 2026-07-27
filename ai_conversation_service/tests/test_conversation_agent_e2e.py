"""Covers the agent-facing surface: the retrieval entry point and both tools.

These were the paths the SDD assumed were covered but weren't — `send_message_with_context`
is the production entry point for the whole feature, and `read_conversation` carries its
own cross-project guard.
"""

from dataclasses import dataclass

import pytest

from ai_conversation_service.agents.conversation_agent import (
    AgentDeps,
    read_conversation,
    search_context,
)
from ai_conversation_service.schemas.retrieval_schemas import ContextHit


@dataclass
class FakeRunContext:
    """Stands in for pydantic_ai's RunContext, which only exposes `deps` to a tool."""

    deps: AgentDeps


class FakeConversation:
    def __init__(self, conversation_id: str, project_id: str, messages=None):
        self.conversation_id = conversation_id
        self.project_id = project_id
        self.messages = messages or []


class FakeTranscripts:
    def __init__(self, conversations: dict[str, FakeConversation]):
        self.conversations = conversations

    async def get_conversation(self, conversation_id: str):
        return self.conversations.get(conversation_id)


async def test_search_context_records_consulted_conversations(
    chunk_index_service, retrieval_service, family_messages
):
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )
    deps = AgentDeps(
        project_id="proj-1",
        conversation_id="conv-current",
        retrieval=retrieval_service,
    )

    hits = await search_context(FakeRunContext(deps), "my family", limit=5)

    assert hits
    assert all(isinstance(hit, ContextHit) for hit in hits)
    assert "conv-family" in deps.consulted
    assert deps.consulted["conv-family"].hit_count >= 1
    assert deps.tool_calls == 1


async def test_read_conversation_refuses_another_project(
    chunk_index_service, retrieval_service, family_messages
):
    """The read tool's own cross-project guard — same risk class as vector isolation."""
    await chunk_index_service.reindex_conversation(
        "conv-foreign", "proj-OTHER", "node-foreign", family_messages, "Foreign"
    )
    deps = AgentDeps(
        project_id="proj-1",
        conversation_id="conv-current",
        retrieval=retrieval_service,
        chunk_index=chunk_index_service,
        transcripts=FakeTranscripts(
            {"conv-foreign": FakeConversation("conv-foreign", "proj-OTHER")}
        ),
    )

    windows = await read_conversation(FakeRunContext(deps), "conv-foreign")

    assert windows == [], "must not return content from another project"


async def test_read_conversation_returns_windows_for_own_project(
    chunk_index_service, retrieval_service, family_messages
):
    await chunk_index_service.reindex_conversation(
        "conv-mine", "proj-1", "node-mine", family_messages, "Mine"
    )
    deps = AgentDeps(
        project_id="proj-1",
        conversation_id="conv-current",
        retrieval=retrieval_service,
        chunk_index=chunk_index_service,
        transcripts=FakeTranscripts(
            {"conv-mine": FakeConversation("conv-mine", "proj-1")}
        ),
    )

    windows = await read_conversation(FakeRunContext(deps), "conv-mine")

    assert windows
    assert any("Dana" in window for window in windows)


async def test_read_conversation_denies_unknown_conversation(retrieval_service):
    deps = AgentDeps(
        project_id="proj-1",
        conversation_id="conv-current",
        retrieval=retrieval_service,
        chunk_index=object(),
        transcripts=FakeTranscripts({}),
    )

    assert await read_conversation(FakeRunContext(deps), "no-such-conv") == []


async def test_graph_expansion_pulls_in_neighbour_conversations(
    chunk_index_service, retrieval_service, projects_client, family_messages
):
    """1-hop expansion: a sibling of a hit node contributes a discounted hit."""
    await chunk_index_service.reindex_conversation(
        "conv-hit", "proj-1", "node-hit", family_messages, "Direct Hit"
    )
    # Deliberately unrelated to the query, so vector search misses it and only the
    # graph edge can surface it — which is the whole point of 1-hop expansion.
    await chunk_index_service.reindex_conversation(
        "conv-neighbour",
        "proj-1",
        "node-neighbour",
        [{"role": "user", "content": "webhook timeout during payment retry backoff"}],
        "Neighbour",
    )
    projects_client._sibling_map = {"node-hit": ["node-neighbour"]}

    hits = await retrieval_service.search(
        project_id="proj-1", query="family nurse", limit=1
    )

    expanded = [hit for hit in hits if hit.via == "graph_expansion"]
    assert expanded, "expected a graph-expansion hit from the sibling node"
    assert any(hit.conversation_id == "conv-neighbour" for hit in expanded)


async def test_send_message_reports_consulted_and_tool_calls(
    chunk_index_service, retrieval_service, reindex_trigger, family_messages
):
    """The production entry point: agent run, persistence, consulted, tool_calls_used."""
    from ai_conversation_service.services.ai_conversation_service.service import (
        AIConversationService,
        ConversationNotFoundError,
    )

    service = AIConversationService.__new__(AIConversationService)
    service._logger = __import__("loguru").logger.bind(service="test")
    service.chunk_index_service = chunk_index_service
    service.context_retrieval_service = retrieval_service
    service.reindex_trigger = reindex_trigger
    service._background_tasks = set()
    service.projects_service_client = None

    stored = FakeConversation("conv-main", "proj-1", [])
    saved: list[int] = []

    async def fake_get_conversation(conversation_id):
        return stored if conversation_id == "conv-main" else None

    async def fake_save(conversation):
        saved.append(len(conversation.messages))

    class FakeResult:
        output = "Dana is a nurse at Rambam."

    class FakeAgent:
        async def run(self, prompt, deps=None, usage_limits=None):
            await search_context(FakeRunContext(deps), "family")
            return FakeResult()

    service.get_conversation = fake_get_conversation
    service._save_conversation = fake_save
    service.conversation_agent = FakeAgent()

    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )

    result = await service.send_message_with_context("conv-main", "what about family?")

    assert result.response == "Dana is a nurse at Rambam."
    assert result.tool_calls_used == 1
    assert any(c.conversation_id == "conv-family" for c in result.consulted)
    assert [message["role"] for message in stored.messages] == ["user", "assistant"]
    assert saved, "conversation must be persisted"

    with pytest.raises(ConversationNotFoundError):
        await service.send_message_with_context("missing", "hello")
