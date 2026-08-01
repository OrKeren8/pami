"""Covers the migration a model change needs.

Vectors of different widths cannot be compared, so retrieval skips any chunk written by a
different embedder. Without a backfill, changing the model left every conversation recorded
before the switch permanently invisible: search kept working and kept returning nothing.
"""

from ai_conversation_service.data.vector_index import CHUNK_COLLECTION
from ai_conversation_service.services.reindex_backfill import (
    reindex_stale_conversations,
)


class FakeConversation:
    def __init__(self, conversation_id, project_id, messages):
        self.conversation_id = conversation_id
        self.project_id = project_id
        self.context_node_id = f"node-of-{conversation_id}"
        self.messages = messages
        self.title = "Dana Nursing"


class FakeTranscripts:
    def __init__(self, conversations):
        self.conversations = conversations

    async def get_conversation(self, conversation_id):
        return self.conversations.get(conversation_id)


async def test_backfill_makes_stale_chunks_searchable_again(
    chunk_index_service, retrieval_service, test_database, family_messages, embedder
):
    await chunk_index_service.reindex_conversation(
        "conv-old", "proj-1", "node-old", family_messages, "Dana Nursing"
    )

    # Stand in for chunks written before a model change: same text, a width the current
    # embedder cannot compare against.
    await test_database[CHUNK_COLLECTION].update_many(
        {"conversation_id": "conv-old"},
        {"$set": {"embedding_model": "old-model@128", "embedding": [0.1] * 128}},
    )

    blinded = await retrieval_service.search(
        project_id="proj-1",
        query="dana nursing",
        exclude_conversation_id="other",
        limit=5,
    )
    assert blinded == [], "stale-width chunks must not be scored"

    transcripts = FakeTranscripts(
        {"conv-old": FakeConversation("conv-old", "proj-1", list(family_messages))}
    )
    reindexed = await reindex_stale_conversations(
        test_database, chunk_index_service, transcripts, limit=10
    )

    assert reindexed == 1
    recovered = await retrieval_service.search(
        project_id="proj-1",
        query="dana nursing",
        exclude_conversation_id="other",
        limit=5,
    )
    assert recovered, "the conversation should be searchable again after the backfill"

    models = await test_database[CHUNK_COLLECTION].distinct(
        "embedding_model", {"conversation_id": "conv-old"}
    )
    assert models == [embedder.model_id]


async def test_backfill_is_a_no_op_when_nothing_is_stale(
    chunk_index_service, test_database, family_messages
):
    """It runs on every start, so a matching index must cost nothing."""
    await chunk_index_service.reindex_conversation(
        "conv-fresh", "proj-1", "node-fresh", family_messages, "Dana Nursing"
    )

    transcripts = FakeTranscripts({})
    assert (
        await reindex_stale_conversations(
            test_database, chunk_index_service, transcripts, limit=10
        )
        == 0
    )


async def test_backfill_drops_chunks_whose_transcript_is_gone(
    chunk_index_service, test_database, family_messages
):
    """Otherwise every start reports work it can never complete."""
    await chunk_index_service.reindex_conversation(
        "conv-orphan", "proj-1", "node-orphan", family_messages, "Dana Nursing"
    )
    await test_database[CHUNK_COLLECTION].update_many(
        {"conversation_id": "conv-orphan"},
        {"$set": {"embedding_model": "old-model@128", "embedding": [0.1] * 128}},
    )

    reindexed = await reindex_stale_conversations(
        test_database, chunk_index_service, FakeTranscripts({}), limit=10
    )

    assert reindexed == 0
    assert (
        await test_database[CHUNK_COLLECTION].count_documents(
            {"conversation_id": "conv-orphan"}
        )
        == 0
    )
