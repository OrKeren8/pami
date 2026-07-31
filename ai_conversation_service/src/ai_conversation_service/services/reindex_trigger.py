from datetime import UTC, datetime

from loguru import logger

from ai_conversation_service.core.config import settings
from ai_conversation_service.services.chunk_index_service import ChunkIndexService
from ai_conversation_service.services.projects_service_client import (
    ProjectsServiceClient,
)
from ai_conversation_service.services.similarity import (
    prune_score_if_unrelated,
    top_k_scores,
)


class ReindexTrigger:
    """Re-indexes a conversation and refreshes its graph links, on a debounce."""

    def __init__(
        self,
        chunk_index_service: ChunkIndexService,
        projects_service_client: ProjectsServiceClient,
    ):
        self._logger = logger.bind(service="ReindexTrigger")
        self._chunk_index_service = chunk_index_service
        self._projects_service_client = projects_service_client

    async def maybe_reindex(
        self,
        conversation_id: str,
        project_id: str,
        node_id: str | None,
        messages: list[dict],
        header: str | None = None,
        force: bool = False,
    ) -> bool:
        """Reindex only once enough new messages have accumulated."""
        if not messages:
            return False

        state = await self._chunk_index_service.state_for(conversation_id)
        last_indexed = state.last_indexed_message_index if state else -1
        new_messages = (len(messages) - 1) - last_indexed

        if not force and new_messages < settings.reindex_message_threshold:
            self._logger.debug(
                f"Skipping reindex of {conversation_id}: {new_messages} new messages "
                f"below threshold {settings.reindex_message_threshold}"
            )
            return False

        refreshed = await self._chunk_index_service.reindex_conversation(
            conversation_id=conversation_id,
            project_id=project_id,
            node_id=node_id,
            messages=messages,
            header=header,
        )
        if not refreshed:
            return False

        await self._refresh_graph_links(project_id, conversation_id, refreshed.node_id)
        return True

    async def _refresh_graph_links(
        self, project_id: str, conversation_id: str, node_id: str | None
    ) -> None:
        if not node_id:
            return

        similarities = await self._chunk_index_service.conversation_similarities(
            project_id, conversation_id
        )
        if not similarities:
            return

        # Keep only peers that exist as context nodes. Conversations the user never
        # turned into a node are still indexed for retrieval, but naming one as a
        # sibling makes projects_service reject the entire payload, losing the valid
        # links along with it.
        known_node_ids = await self._projects_service_client.get_project_node_ids(
            project_id
        )
        if known_node_ids is not None:
            if node_id not in known_node_ids:
                self._logger.info(
                    f"Skipping score push: node {node_id} is not a context node"
                )
                return
            dropped = set(similarities).difference(known_node_ids)
            if dropped:
                self._logger.info(
                    f"Dropping {len(dropped)} peers that are not context nodes"
                )
            similarities = {
                peer: value
                for peer, value in similarities.items()
                if peer in known_node_ids
            }
        if not similarities:
            return

        state = await self._chunk_index_service.state_for(conversation_id)
        model_id = state.embedding_model if state else ""
        scores = top_k_scores(similarities, model_id, settings.sibling_top_k)

        # A peer that already has a link and has now drifted below the floor must be
        # named explicitly, because absence means "retain" on the projects side and the
        # link could otherwise never be pruned. Peers that are merely outside top-k are
        # left unmentioned so the edge survives while either side still ranks the other.
        for peer_node_id in await self._projects_service_client.get_sibling_node_ids(
            node_id
        ):
            if peer_node_id in scores or peer_node_id not in similarities:
                continue
            prune = prune_score_if_unrelated(similarities[peer_node_id], model_id)
            if prune is not None:
                scores[peer_node_id] = prune

        pushed = await self._projects_service_client.push_sibling_scores(
            node_id, scores
        )
        if pushed:
            await self._chunk_index_service.mark_scored(
                conversation_id, datetime.now(UTC)
            )
        self._logger.info(
            f"Refreshed {len(scores)} sibling scores for node {node_id} "
            f"(pushed={pushed})"
        )
