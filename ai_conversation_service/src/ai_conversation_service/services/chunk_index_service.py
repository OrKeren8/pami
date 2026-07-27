from datetime import UTC, datetime

import numpy as np
from loguru import logger
from pymongo import UpdateOne
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

from ai_conversation_service.data.vector_index import (
    CHUNK_COLLECTION,
    VECTOR_INDEX_NAME,
)
from ai_conversation_service.models.conversation_chunk import ConversationChunk
from ai_conversation_service.models.conversation_index_state import (
    ConversationIndexState,
)
from ai_conversation_service.schemas.retrieval_schemas import ContextHit
from ai_conversation_service.services.embedder import Embedder
from ai_conversation_service.services.similarity import cosine

SCAN_LIMIT = 5000
STATE_COLLECTION = "conversation_index_state"


class ChunkIndexService:
    """Indexes conversations as embedded message windows and searches them."""

    def __init__(
        self,
        embedder: Embedder,
        database: AsyncDatabase,
        window_size: int = 4,
        window_overlap: int = 1,
    ):
        self._logger = logger.bind(service="ChunkIndexService")
        self._embedder = embedder
        self._database = database
        self._window_size = window_size
        self._window_step = max(1, window_size - window_overlap)

    async def reindex_conversation(
        self,
        conversation_id: str,
        project_id: str,
        node_id: str | None,
        messages: list[dict],
        header: str | None = None,
    ) -> ConversationIndexState | None:
        """Re-chunk and re-embed a conversation, then refresh its index state."""
        windows = self._build_windows(messages)
        if not windows:
            return None

        vectors = await self._embedder.embed([text for _, _, text in windows])
        await self._upsert_chunks(
            conversation_id=conversation_id,
            project_id=project_id,
            node_id=node_id,
            windows=windows,
            vectors=vectors,
        )

        centroid = self._centroid(vectors)
        state = await self._advance_index_state(
            conversation_id=conversation_id,
            project_id=project_id,
            node_id=node_id,
            header=header,
            centroid=centroid,
            last_index=len(messages) - 1,
            message_count=len(messages),
        )
        self._logger.info(
            f"Indexed conversation {conversation_id}: {len(windows)} chunks, "
            f"{len(messages)} messages"
        )
        return state

    async def search(
        self,
        project_id: str,
        query_vector: list[float],
        limit: int = 5,
        exclude_conversation_id: str | None = None,
    ) -> list[ContextHit]:
        """Vector-search chunks within one project. Never crosses project boundaries."""
        search_filter: dict = {"project_id": project_id}
        pipeline = [
            {
                "$vectorSearch": {
                    "index": VECTOR_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": max(50, limit * 20),
                    "limit": limit * 3,
                    "filter": search_filter,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "conversation_id": 1,
                    "node_id": 1,
                    "text": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        rows: list[dict] = []
        try:
            cursor = await self._database[CHUNK_COLLECTION].aggregate(pipeline)
            rows = await cursor.to_list()
        except OperationFailure as error:
            self._logger.warning(
                f"Vector search rejected (code {error.code}); scanning in-process"
            )

        if not rows:
            # The Atlas index takes ~25s to become queryable after creation, so a
            # fresh deployment would otherwise return nothing at all.
            return await self._scan_search(
                project_id, query_vector, limit, exclude_conversation_id
            )

        hits: list[ContextHit] = []
        for row in rows:
            if row.get("conversation_id") == exclude_conversation_id:
                continue
            hits.append(
                self._to_hit(
                    row["conversation_id"],
                    row.get("node_id"),
                    row.get("text", ""),
                    float(row.get("score", 0.0)),
                    "vector",
                )
            )
            if len(hits) >= limit:
                break
        return await self._attach_headers(hits)

    async def chunks_for_conversations(
        self,
        project_id: str,
        conversation_ids: list[str],
        query_vector: list[float],
        limit: int = 3,
    ) -> list[ContextHit]:
        """Best-matching chunks from named conversations, for 1-hop graph expansion."""
        if not conversation_ids:
            return []

        chunks = await ConversationChunk.find(
            ConversationChunk.project_id == project_id,
            {"conversation_id": {"$in": conversation_ids}},
        ).to_list()

        scored = self._rank_by_cosine(query_vector, chunks)
        return await self._attach_headers(
            [
                self._to_hit(
                    chunk.conversation_id,
                    chunk.node_id,
                    chunk.text,
                    score,
                    "graph_expansion",
                )
                for score, chunk in scored[:limit]
            ]
        )

    async def read_window(
        self,
        conversation_id: str,
        around_message: int,
        radius: int = 6,
        project_id: str | None = None,
    ) -> list[str]:
        """Chunk texts around a message index. Pass project_id to enforce scoping here."""
        query: dict = {"conversation_id": conversation_id}
        if project_id:
            query["project_id"] = project_id
        if around_message >= 0:
            query["message_end"] = {"$gte": around_message - radius}
            query["message_start"] = {"$lte": around_message + radius}

        chunks = await ConversationChunk.find(query).to_list()
        return [
            chunk.text
            for chunk in sorted(chunks, key=lambda chunk: chunk.message_start)
        ]

    async def conversation_similarities(
        self, project_id: str, conversation_id: str
    ) -> dict[str, float]:
        """Cosine between one conversation's centroid and every peer's, by node id."""
        states = await ConversationIndexState.find(
            ConversationIndexState.project_id == project_id
        ).to_list()

        source = next(
            (s for s in states if s.conversation_id == conversation_id and s.embedding),
            None,
        )
        if not source:
            return {}

        similarities: dict[str, float] = {}
        for state in states:
            if state.conversation_id == conversation_id or not state.embedding:
                continue
            if state.embedding_model != source.embedding_model:
                continue
            if not state.node_id:
                continue
            similarities[state.node_id] = cosine(source.embedding, state.embedding)
        return similarities

    async def conversation_ids_for_nodes(
        self, project_id: str, node_ids: list[str]
    ) -> list[str]:
        """Conversation ids belonging to the given context nodes."""
        if not node_ids:
            return []
        states = await ConversationIndexState.find(
            ConversationIndexState.project_id == project_id,
            {"node_id": {"$in": node_ids}},
        ).to_list()
        return [state.conversation_id for state in states]

    async def mark_scored(self, conversation_id: str, when: datetime) -> None:
        """Record that sibling scores were pushed, so writes stay owned by this service."""
        await ConversationIndexState.find_one(
            ConversationIndexState.conversation_id == conversation_id
        ).update({"$set": {"last_scored_at": when}})

    async def state_for(self, conversation_id: str) -> ConversationIndexState | None:
        """Current index bookkeeping for a conversation."""
        return await ConversationIndexState.find_one(
            ConversationIndexState.conversation_id == conversation_id
        )

    async def headers_for_nodes(
        self, project_id: str, node_ids: list[str]
    ) -> dict[str, str]:
        """Node id to header, for priming the agent with what it can search."""
        if not node_ids:
            return {}
        states = await ConversationIndexState.find(
            ConversationIndexState.project_id == project_id,
            {"node_id": {"$in": node_ids}},
        ).to_list()
        return {s.node_id: s.header for s in states if s.node_id and s.header}

    async def delete_conversation(self, conversation_id: str) -> None:
        """Drop a conversation's index state first, then its chunks.

        State-before-chunks ordering keeps a crash between the two harmless: the
        lookups that surface a conversation key off the index state, so leftover
        chunks become unreachable rather than serving a half-deleted conversation.
        """
        await ConversationIndexState.find(
            ConversationIndexState.conversation_id == conversation_id
        ).delete()
        await ConversationChunk.find(
            ConversationChunk.conversation_id == conversation_id
        ).delete()
        self._logger.info(f"Removed index entries for conversation {conversation_id}")

    async def _scan_search(
        self,
        project_id: str,
        query_vector: list[float],
        limit: int,
        exclude_conversation_id: str | None,
    ) -> list[ContextHit]:
        """Rank a project's chunks in-process; used when the vector index cannot serve."""
        query: dict = {"project_id": project_id}
        if exclude_conversation_id:
            query["conversation_id"] = {"$ne": exclude_conversation_id}

        candidates = await ConversationChunk.find(query).limit(SCAN_LIMIT).to_list()
        if not candidates:
            return []
        if len(candidates) == SCAN_LIMIT:
            self._logger.warning(
                f"In-process scan hit the {SCAN_LIMIT}-chunk cap for project "
                f"{project_id}; results are partial until the vector index serves"
            )

        scored = self._rank_by_cosine(query_vector, candidates)
        self._logger.info(
            f"In-process scan over {len(candidates)} chunks for project {project_id}"
        )
        return await self._attach_headers(
            [
                self._to_hit(
                    chunk.conversation_id, chunk.node_id, chunk.text, score, "vector"
                )
                for score, chunk in scored[:limit]
            ]
        )

    def _rank_by_cosine(
        self, query_vector: list[float], chunks: list[ConversationChunk]
    ) -> list[tuple[float, ConversationChunk]]:
        return sorted(
            (
                (cosine(query_vector, chunk.embedding), chunk)
                for chunk in chunks
                if chunk.embedding
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )

    def _to_hit(
        self,
        conversation_id: str,
        node_id: str | None,
        text: str,
        score: float,
        via: str,
    ) -> ContextHit:
        return ContextHit(
            conversation_id=conversation_id,
            node_id=node_id,
            snippet=self._snippet(text),
            score=score,
            via=via,
        )

    async def _attach_headers(self, hits: list[ContextHit]) -> list[ContextHit]:
        conversation_ids = sorted({hit.conversation_id for hit in hits})
        if not conversation_ids:
            return hits

        states = await ConversationIndexState.find(
            {"conversation_id": {"$in": conversation_ids}}
        ).to_list()
        headers = {state.conversation_id: state.header for state in states}
        for hit in hits:
            hit.header = headers.get(hit.conversation_id)
        return hits

    def _build_windows(self, messages: list[dict]) -> list[tuple[int, int, str]]:
        usable = [
            (index, message)
            for index, message in enumerate(messages or [])
            if str(self._content_of(message)).strip()
        ]
        if not usable:
            return []

        windows: list[tuple[int, int, str]] = []
        for offset in range(0, len(usable), self._window_step):
            window = usable[offset : offset + self._window_size]
            if not window:
                break
            text = "\n".join(
                f"{self._role_of(message)}: {self._content_of(message)}"
                for _, message in window
            )
            windows.append((window[0][0], window[-1][0], text))
            if offset + self._window_size >= len(usable):
                break
        return windows

    async def _upsert_chunks(
        self,
        conversation_id: str,
        project_id: str,
        node_id: str | None,
        windows: list[tuple[int, int, str]],
        vectors: list[list[float]],
    ) -> None:
        """One round trip for every window, keyed on the unique window index."""
        now = datetime.now(UTC)
        operations = [
            UpdateOne(
                {"conversation_id": conversation_id, "message_start": start},
                {
                    "$set": {
                        "conversation_id": conversation_id,
                        "node_id": node_id,
                        "project_id": project_id,
                        "text": text,
                        "message_start": start,
                        "message_end": end,
                        "embedding": vector,
                        "embedding_model": self._embedder.model_id,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            for (start, end, text), vector in zip(windows, vectors)
        ]
        if operations:
            await self._database[CHUNK_COLLECTION].bulk_write(operations, ordered=False)

    async def _advance_index_state(
        self,
        conversation_id: str,
        project_id: str,
        node_id: str | None,
        header: str | None,
        centroid: list[float],
        last_index: int,
        message_count: int,
    ) -> ConversationIndexState | None:
        """Advance the index state atomically.

        `$max` keeps the message counters monotonic without a read-modify-write, so a
        background reindex and a forced one cannot interleave and regress them.
        """
        updates: dict = {
            "project_id": project_id,
            "embedding": centroid,
            "embedding_model": self._embedder.model_id,
            "updated_at": datetime.now(UTC),
        }
        if node_id:
            updates["node_id"] = node_id
        if header:
            updates["header"] = header

        await self._database[STATE_COLLECTION].find_one_and_update(
            {"conversation_id": conversation_id},
            {
                "$set": updates,
                "$max": {
                    "last_indexed_message_index": last_index,
                    "message_count_at_index": message_count,
                },
            },
            upsert=True,
        )
        return await self.state_for(conversation_id)

    @staticmethod
    def _centroid(vectors: list[list[float]]) -> list[float]:
        matrix = np.asarray(vectors, dtype=np.float32)
        mean = matrix.mean(axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            return mean.tolist()
        return (mean / norm).tolist()

    @staticmethod
    def _snippet(text: str, limit: int = 400) -> str:
        collapsed = " ".join(text.split())
        return collapsed[:limit]

    @staticmethod
    def _role_of(message) -> str:
        if isinstance(message, dict):
            return str(message.get("role") or "user")
        return str(getattr(message, "role", "user"))

    @staticmethod
    def _content_of(message) -> str:
        if isinstance(message, dict):
            return str(message.get("content") or "")
        return str(getattr(message, "content", "") or "")
