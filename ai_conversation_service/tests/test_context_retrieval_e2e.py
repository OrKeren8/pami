"""Covers the Testing Strategy scenarios in docs/sdd-conversation-context-retrieval.md.

Runs through the real ChunkIndexService / ContextRetrievalService / ReindexTrigger
against a real Mongo test database. Only the embedder and projects_service HTTP calls
are substituted, and both are out-of-process boundaries.
"""

import pytest

from ai_conversation_service.core.config import settings
from ai_conversation_service.models.conversation_chunk import ConversationChunk
from ai_conversation_service.services.context_retrieval_service import (
    ContextRetrievalService,
)
from ai_conversation_service.services.similarity import (
    MIN_CORRELATION_SCORE,
    top_k_scores,
)


async def test_finds_context_in_another_conversation(
    chunk_index_service, retrieval_service, family_messages, billing_messages
):
    """SDD scenario 1 - the motivating case."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing Career"
    )
    await chunk_index_service.reindex_conversation(
        "conv-billing", "proj-1", "node-billing", billing_messages, "Payment Retry"
    )

    hits = await retrieval_service.search(
        project_id="proj-1",
        query="what do I know about my family?",
        exclude_conversation_id="conv-billing",
    )

    assert hits, "expected at least one hit from the family conversation"
    assert hits[0].conversation_id == "conv-family"
    assert "Dana" in hits[0].snippet
    assert hits[0].header == "Dana Nursing Career"
    assert all(hit.conversation_id != "conv-billing" for hit in hits)


async def test_young_conversation_becomes_searchable(
    chunk_index_service, reindex_trigger, family_messages
):
    """SDD scenario 2 - reachable within a few messages, without a full-graph pass."""
    short = family_messages[:1]
    assert (
        await reindex_trigger.maybe_reindex(
            conversation_id="conv-young",
            project_id="proj-1",
            node_id="node-young",
            messages=short,
            header="Young Conversation",
        )
        is False
    )

    grew = await reindex_trigger.maybe_reindex(
        conversation_id="conv-young",
        project_id="proj-1",
        node_id="node-young",
        messages=family_messages,
        header="Young Conversation",
    )
    assert grew is True

    chunks = await ConversationChunk.find(
        ConversationChunk.conversation_id == "conv-young"
    ).to_list()
    assert chunks


async def test_retrieval_never_crosses_projects(
    chunk_index_service, retrieval_service, family_messages
):
    """SDD scenario 3 - the highest-severity failure mode."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )

    hits = await retrieval_service.search(
        project_id="proj-OTHER", query="what do I know about my family?"
    )

    assert hits == []


async def test_retrieval_degrades_when_embedder_fails(
    chunk_index_service, projects_client, family_messages
):
    """SDD scenario 4 - a broken embedder must not raise at the retrieval boundary."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )

    class BrokenEmbedder:
        dimensions = 384
        model_id = "broken@384"

        async def embed(self, texts):
            raise RuntimeError("model not loaded")

    service = ContextRetrievalService(
        BrokenEmbedder(), chunk_index_service, projects_client
    )
    with pytest.raises(RuntimeError):
        await service.search(project_id="proj-1", query="family")


async def test_graph_refresh_is_bounded_and_prunes_unrelated(
    chunk_index_service,
    reindex_trigger,
    projects_client,
    family_messages,
    billing_messages,
):
    """SDD scenario 5 - top-K bound, and unrelated topics score below the threshold."""
    await chunk_index_service.reindex_conversation(
        "conv-billing", "proj-1", "node-billing", billing_messages, "Payment Retry"
    )
    await reindex_trigger.maybe_reindex(
        conversation_id="conv-family",
        project_id="proj-1",
        node_id="node-family",
        messages=family_messages,
        header="Dana Nursing",
        force=True,
    )

    assert projects_client.pushed, "expected sibling scores to be pushed"
    node_id, scores = projects_client.pushed[-1]
    assert node_id == "node-family"
    assert len(scores) <= settings.sibling_top_k
    assert scores.get("node-billing", 0) < MIN_CORRELATION_SCORE


async def test_budget_caps_conversations_consulted(
    chunk_index_service, retrieval_service, family_messages
):
    """SDD scenario 6 - never consult more conversations than the budget allows."""
    for index in range(settings.retrieval_max_conversations + 3):
        await chunk_index_service.reindex_conversation(
            f"conv-{index}",
            "proj-1",
            f"node-{index}",
            family_messages,
            f"Family Conversation {index}",
        )

    hits = await retrieval_service.search(
        project_id="proj-1", query="family sister nurse", limit=20
    )

    consulted = {hit.conversation_id for hit in hits}
    assert len(consulted) <= settings.retrieval_max_conversations


async def test_drifted_link_is_rescored_even_outside_top_k(
    chunk_index_service, projects_client, family_messages, billing_messages
):
    """A peer that already has a link must be scored even when top-K excludes it.

    Absence means "retain" on the projects side, so if top-K silently drops a peer
    whose similarity has collapsed, its stale link could never be pruned.
    """
    from ai_conversation_service.services.reindex_trigger import ReindexTrigger

    for index in range(settings.sibling_top_k):
        await chunk_index_service.reindex_conversation(
            f"conv-peer-{index}",
            "proj-1",
            f"node-peer-{index}",
            family_messages,
            f"Family Peer {index}",
        )
    await chunk_index_service.reindex_conversation(
        "conv-stale", "proj-1", "node-stale", billing_messages, "Drifted Away"
    )

    projects_client._sibling_map = {"node-source": ["node-stale"]}
    trigger = ReindexTrigger(chunk_index_service, projects_client)
    await trigger.maybe_reindex(
        conversation_id="conv-source",
        project_id="proj-1",
        node_id="node-source",
        messages=family_messages,
        header="Source Conversation",
        force=True,
    )

    _, scores = projects_client.pushed[-1]
    assert "node-stale" in scores, "drifted peer must be re-scored so it can be pruned"
    assert scores["node-stale"] < MIN_CORRELATION_SCORE


async def test_atlas_vector_search_path_returns_hits(
    vector_index, chunk_index_service, embedder, family_messages, billing_messages
):
    """Exercise the real `$vectorSearch` pipeline, not the in-process fallback."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-vec", "node-family", family_messages, "Dana Nursing"
    )
    await chunk_index_service.reindex_conversation(
        "conv-billing", "proj-vec", "node-billing", billing_messages, "Payment Retry"
    )

    query_vector = (await embedder.embed(["family sister nurse"]))[0]
    hits = await chunk_index_service.search("proj-vec", query_vector, limit=5)

    assert hits
    assert hits[0].conversation_id == "conv-family"
    assert all(hit.via == "vector" for hit in hits)


async def test_peers_that_are_not_nodes_are_dropped_from_the_push(
    chunk_index_service, reindex_trigger, projects_client, family_messages
):
    """One non-node peer must not sink the whole payload.

    A conversation the user never turned into a node keeps a synthetic id. Naming it as
    a sibling makes projects_service answer 422 and reject every score in the request,
    so the valid links are lost too.
    """
    await chunk_index_service.reindex_conversation(
        "conv-real", "proj-1", "node-real", family_messages, "Real Node"
    )
    await chunk_index_service.reindex_conversation(
        "conv-orphan",
        "proj-1",
        "chat-session-1785224521262",
        family_messages,
        "Never Materialised",
    )
    projects_client.known_node_ids = {"node-real", "node-source"}

    await reindex_trigger.maybe_reindex(
        conversation_id="conv-source",
        project_id="proj-1",
        node_id="node-source",
        messages=family_messages,
        header="Source",
        force=True,
    )

    assert projects_client.pushed, "a push should still happen"
    _, scores = projects_client.pushed[-1]
    assert "chat-session-1785224521262" not in scores
    assert "node-real" in scores


async def test_chunk_upsert_is_idempotent(chunk_index_service, family_messages):
    """Re-indexing the same messages must not duplicate chunks."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )
    first = await ConversationChunk.find(
        ConversationChunk.conversation_id == "conv-family"
    ).count()

    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )
    second = await ConversationChunk.find(
        ConversationChunk.conversation_id == "conv-family"
    ).count()

    assert first == second


async def test_deleting_a_conversation_removes_its_index(
    chunk_index_service, family_messages
):
    """Orphaned chunks would keep deleted conversations searchable."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )

    await chunk_index_service.delete_conversation("conv-family")

    assert (
        await ConversationChunk.find(
            ConversationChunk.conversation_id == "conv-family"
        ).count()
        == 0
    )
    assert await chunk_index_service.state_for("conv-family") is None


async def test_read_window_returns_surrounding_chunks(
    chunk_index_service, family_messages
):
    """read_conversation must widen around a hit, not return a single chunk."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )

    windows = await chunk_index_service.read_window("conv-family", around_message=0)

    assert windows
    assert any("Dana" in window for window in windows)


async def test_scores_only_compare_matching_embedding_models(
    chunk_index_service, family_messages, billing_messages
):
    """Mixing vector spaces would make every score meaningless."""
    await chunk_index_service.reindex_conversation(
        "conv-family", "proj-1", "node-family", family_messages, "Dana Nursing"
    )
    await chunk_index_service.reindex_conversation(
        "conv-billing", "proj-1", "node-billing", billing_messages, "Payment Retry"
    )

    stale = await chunk_index_service.state_for("conv-billing")
    stale.embedding_model = "some-other-model@768"
    await stale.save()

    similarities = await chunk_index_service.conversation_similarities(
        "proj-1", "conv-family"
    )

    assert "node-billing" not in similarities
    assert top_k_scores(similarities, "deterministic-test@384", 8) == {}


async def test_mismatched_vector_widths_do_not_break_search(
    chunk_index_service, retrieval_service, family_messages
):
    """A half-migrated index must degrade, not raise.

    Changing the embedding model changes the vector width, so during a re-index the
    collection holds both widths. Comparing them used to raise inside numpy and would take
    down every search that touched a stale chunk.
    """
    from ai_conversation_service.data.vector_index import CHUNK_COLLECTION
    from ai_conversation_service.services.similarity import cosine

    assert cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0
    assert cosine([], [1.0]) == 0.0

    await chunk_index_service.reindex_conversation(
        "conv-current-model", "proj-mixed", "node-a", family_messages, "Current"
    )
    await chunk_index_service._database[CHUNK_COLLECTION].insert_one(
        {
            "conversation_id": "conv-stale-model",
            "project_id": "proj-mixed",
            "node_id": "node-b",
            "text": "a chunk left behind by the previous embedding model",
            "message_start": 0,
            "message_end": 1,
            "embedding": [0.1] * 8,
            "embedding_model": "previous-model@8",
        }
    )

    hits = await retrieval_service.search(project_id="proj-mixed", query="nurse Dana")

    assert any(hit.conversation_id == "conv-current-model" for hit in hits)
    assert all(hit.conversation_id != "conv-stale-model" for hit in hits)
