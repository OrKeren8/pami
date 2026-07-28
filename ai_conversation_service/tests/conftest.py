import asyncio
import hashlib

import pytest
import pytest_asyncio
from beanie import init_beanie
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from ai_conversation_service.core.config import settings
from ai_conversation_service.data.vector_index import (
    CHUNK_COLLECTION,
    VECTOR_INDEX_NAME,
    ensure_vector_index,
)
from ai_conversation_service.models.conversation_chunk import ConversationChunk
from ai_conversation_service.models.conversation_index_state import (
    ConversationIndexState,
)
from ai_conversation_service.services.chunk_index_service import ChunkIndexService
from ai_conversation_service.services.context_retrieval_service import (
    ContextRetrievalService,
)
from ai_conversation_service.services.reindex_trigger import ReindexTrigger

TEST_DATABASE_NAME = "pami_test"
EMBEDDING_DIMENSIONS = 384

VOCABULARY = (
    "family sister brother mother father dana yossi avi nurse hospital haifa "
    "payment billing webhook retry refactor timeout queue backoff pilot"
).split()


class DeterministicEmbedder:
    """Embeds by term overlap so tests are reproducible and need no model download."""

    dimensions = EMBEDDING_DIMENSIONS
    model_id = "deterministic-test@384"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for index, term in enumerate(VOCABULARY):
            if term in lowered:
                vector[index] = 1.0
        # Keep unrelated texts from collapsing onto the zero vector.
        digest = hashlib.sha256(lowered.encode()).digest()
        for offset, byte in enumerate(digest[:16]):
            vector[len(VOCABULARY) + offset] = (byte / 255.0) * 0.05
        return vector


class RecordingProjectsClient:
    """Captures pushed sibling scores instead of calling projects_service."""

    def __init__(self, sibling_map: dict[str, list[str]] | None = None):
        self.pushed: list[tuple[str, dict[str, int]]] = []
        self._sibling_map = sibling_map or {}
        # conversation_id -> the node that owns it, as projects_service would report
        self._node_for_conversation: dict[str, str] = {}

    async def get_node_id_for_conversation(
        self, project_id: str, conversation_id: str
    ) -> str | None:
        return self._node_for_conversation.get(conversation_id)

    async def push_sibling_scores(
        self, node_id: str, scores: dict, source: str = "embedding"
    ) -> bool:
        self.pushed.append((node_id, scores))
        return True

    async def get_sibling_node_ids(self, node_id: str) -> list[str]:
        return self._sibling_map.get(node_id, [])

    async def get_project_metadata(self, project_id: str):
        return None


@pytest_asyncio.fixture
async def test_database():
    """Real Mongo, isolated database, dropped afterwards. Skips if unreachable."""
    client = AsyncMongoClient(settings.mongodb_url, serverSelectionTimeoutMS=8000)
    try:
        await client.admin.command("ping")
    except PyMongoError as error:
        await client.close()
        pytest.skip(f"MongoDB unreachable: {type(error).__name__}")

    database = client[TEST_DATABASE_NAME]
    await init_beanie(
        database=database,
        document_models=[ConversationChunk, ConversationIndexState],
    )
    await ConversationChunk.delete_all()
    await ConversationIndexState.delete_all()

    yield database

    await ConversationChunk.delete_all()
    await ConversationIndexState.delete_all()
    await client.close()


@pytest_asyncio.fixture
async def vector_index(test_database):
    """Ensure the Atlas vector index exists and is queryable, else skip.

    Without this the `$vectorSearch` branch is never exercised and every retrieval
    test silently runs the in-process fallback instead.
    """
    if not await ensure_vector_index(test_database, EMBEDDING_DIMENSIONS):
        pytest.skip("Atlas vector search unavailable on this cluster")

    collection = test_database[CHUNK_COLLECTION]
    for _ in range(24):
        cursor = await collection.list_search_indexes()
        indexes = await cursor.to_list()
        if any(
            index.get("name") == VECTOR_INDEX_NAME and index.get("queryable")
            for index in indexes
        ):
            return True
        await asyncio.sleep(5)
    pytest.skip("vector index did not become queryable in time")


@pytest.fixture
def embedder():
    return DeterministicEmbedder()


@pytest.fixture
def chunk_index_service(embedder, test_database):
    return ChunkIndexService(embedder, test_database)


@pytest.fixture
def projects_client():
    return RecordingProjectsClient()


@pytest.fixture
def retrieval_service(embedder, chunk_index_service, projects_client):
    return ContextRetrievalService(embedder, chunk_index_service, projects_client)


@pytest.fixture
def reindex_trigger(chunk_index_service, projects_client):
    return ReindexTrigger(chunk_index_service, projects_client)


@pytest.fixture
def family_messages():
    return [
        {
            "role": "user",
            "content": "My sister Dana started working as a nurse at Rambam hospital",
        },
        {"role": "assistant", "content": "That is great news about Dana."},
        {"role": "user", "content": "She moved to Haifa with her husband Yossi"},
        {"role": "assistant", "content": "Congratulations to Dana and Yossi."},
    ]


@pytest.fixture
def billing_messages():
    return [
        {"role": "user", "content": "Refactor the payment retry logic in billing"},
        {"role": "assistant", "content": "Use exponential backoff with a queue."},
        {"role": "user", "content": "The webhook handler hits a timeout"},
        {"role": "assistant", "content": "Move it to a background job."},
    ]
