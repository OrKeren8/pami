import asyncio

from loguru import logger

from ai_conversation_service.core.config import settings
from ai_conversation_service.schemas.retrieval_schemas import ContextHit
from ai_conversation_service.services.chunk_index_service import ChunkIndexService
from ai_conversation_service.services.embedder import Embedder
from ai_conversation_service.services.projects_service_client import (
    ProjectsServiceClient,
)

GRAPH_EXPANSION_WEIGHT = 0.7


class ContextRetrievalService:
    """Finds context in other conversations: vector search plus 1-hop graph expansion."""

    def __init__(
        self,
        embedder: Embedder,
        chunk_index_service: ChunkIndexService,
        projects_service_client: ProjectsServiceClient,
    ):
        self._logger = logger.bind(service="ContextRetrievalService")
        self._embedder = embedder
        self._chunk_index_service = chunk_index_service
        self._projects_service_client = projects_service_client

    async def search(
        self,
        project_id: str,
        query: str,
        exclude_conversation_id: str | None = None,
        limit: int = 5,
    ) -> list[ContextHit]:
        """Search the project's other conversations, expanded one hop over the graph."""
        query_vector = (await self._embedder.embed([query]))[0]

        hits = await self._chunk_index_service.search(
            project_id=project_id,
            query_vector=query_vector,
            limit=limit,
            exclude_conversation_id=exclude_conversation_id,
        )

        expanded = await self._expand_over_graph(
            project_id=project_id,
            hits=hits,
            query_vector=query_vector,
            exclude_conversation_id=exclude_conversation_id,
        )

        merged = self._apply_budget(hits + expanded)
        self._logger.info(
            f"Retrieval for project {project_id}: {len(hits)} vector hits, "
            f"{len(expanded)} expanded, {len(merged)} kept"
        )
        return merged

    async def _expand_over_graph(
        self,
        project_id: str,
        hits: list[ContextHit],
        query_vector: list[float],
        exclude_conversation_id: str | None,
    ) -> list[ContextHit]:
        node_ids = {hit.node_id for hit in hits if hit.node_id}
        if not node_ids:
            return []

        sibling_lists = await asyncio.gather(
            *(
                self._projects_service_client.get_sibling_node_ids(node_id)
                for node_id in node_ids
            )
        )
        neighbour_node_ids = {
            sibling_id for siblings in sibling_lists for sibling_id in siblings
        }
        neighbour_node_ids.difference_update(node_ids)
        if not neighbour_node_ids:
            return []

        seen_conversations = {hit.conversation_id for hit in hits}
        neighbour_conversations = (
            await self._chunk_index_service.conversation_ids_for_nodes(
                project_id, sorted(neighbour_node_ids)
            )
        )
        candidates = [
            conversation_id
            for conversation_id in neighbour_conversations
            if conversation_id not in seen_conversations
            and conversation_id != exclude_conversation_id
        ]

        expanded = await self._chunk_index_service.chunks_for_conversations(
            project_id=project_id,
            conversation_ids=candidates,
            query_vector=query_vector,
        )
        for hit in expanded:
            hit.score = hit.score * GRAPH_EXPANSION_WEIGHT
        return expanded

    def _apply_budget(self, hits: list[ContextHit]) -> list[ContextHit]:
        ranked = sorted(hits, key=lambda hit: hit.score, reverse=True)

        kept: list[ContextHit] = []
        conversations: set[str] = set()
        approximate_tokens = 0

        for hit in ranked:
            if (
                hit.conversation_id not in conversations
                and len(conversations) >= settings.retrieval_max_conversations
            ):
                continue
            hit_tokens = len(hit.snippet) // 4
            if approximate_tokens + hit_tokens > settings.retrieval_max_injected_tokens:
                self._logger.info(
                    f"Dropped {len(ranked) - len(kept)} hits for token budget"
                )
                break
            conversations.add(hit.conversation_id)
            approximate_tokens += hit_tokens
            kept.append(hit)

        return kept
