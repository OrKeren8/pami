from typing import Dict, Iterable, List, Optional
from datetime import datetime
from loguru import logger
import aiohttp
import traceback

from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.models.context_tree import ContextTreeNode, SiblingLink
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
    SiblingLinkPayload,
    SiblingScorePayload,
)
from projects_service.core.config import settings


class AIOrganizationError(Exception):
    """Raised when the AI organization service fails to provide a usable response."""


class UnknownSiblingError(Exception):
    """Raised when a sibling score references a node outside the project."""


class ContextTreeService:
    """Service for sibling-link graph business logic driven by AI scores."""

    _MIN_CORRELATION_SCORE = 30

    def __init__(self, context_tree_repository: ContextTreeRepository):
        self._logger = logger.bind(service="ContextTreeService")
        self._context_tree_repository = context_tree_repository

    @staticmethod
    def _ai_base_url() -> str:
        raw = str(getattr(settings, "ai_service_url", "") or "").rstrip("/")
        if raw.endswith("/ai"):
            return raw
        return f"{raw}/ai"

    @staticmethod
    def _node_id(node: ContextTreeNode) -> str:
        return str(getattr(node, "id"))

    @staticmethod
    def _clamp_score(score: int) -> int:
        return max(0, min(100, int(score)))

    def _normalize_topics(self, topics: Optional[Iterable[str]]) -> List[str]:
        seen = set()
        normalized = []
        for topic in topics or []:
            token = str(topic).strip().lower()
            if not token or token in seen:
                continue
            seen.add(token)
            normalized.append(token)
        return normalized

    def _get_link_map(self, node: ContextTreeNode) -> Dict[str, int]:
        link_map: Dict[str, int] = {}
        for link in getattr(node, "sibling_links", []) or []:
            sibling_id = str(getattr(link, "sibling_id", "")).strip()
            if not sibling_id:
                continue
            score = getattr(link, "correlation_score", None)
            if score is None and isinstance(link, dict):
                score = link.get("correlation_score")

            if score is None:
                continue
            score = self._clamp_score(score)
            if score >= self._MIN_CORRELATION_SCORE:
                link_map[sibling_id] = score
        return link_map

    def _serialize_link_map(self, link_map: Dict[str, int]) -> List[SiblingLink]:
        serialized = []
        for sibling_id in sorted(link_map.keys()):
            score = self._clamp_score(link_map[sibling_id])
            if score < self._MIN_CORRELATION_SCORE:
                continue
            serialized.append(
                SiblingLink(sibling_id=sibling_id, correlation_score=score)
            )
        return serialized

    async def _persist_node_fields(self, node: ContextTreeNode, fields: dict) -> None:
        """Write only the named fields.

        This used to mutate the in-memory node and call save(), which replaces the whole
        document. The AI organizer loads a node, spends seconds in an LLM call, then persists
        header/summary/topics - and the save silently reverted any sibling_links written by
        the embedding scorer during that window. That is why links appeared and then
        disappeared. A field-scoped update cannot clobber a concurrent writer's other fields.
        """
        for key, value in fields.items():
            setattr(node, key, value)
        await self._context_tree_repository.update(self._node_id(node), fields)

    def _merge_scores(
        self, existing: Dict[str, int], fresh: Dict[str, int]
    ) -> Dict[str, int]:
        """Freshest score wins; peers absent from `fresh` keep their existing score."""
        merged = dict(existing)
        for peer_id, score in fresh.items():
            if score >= self._MIN_CORRELATION_SCORE:
                merged[peer_id] = score
            else:
                merged.pop(peer_id, None)
        return merged

    async def _recompute_weighted_links_for_node(
        self,
        project_id: str,
        node_id: str,
        include_peer_scores: Optional[Dict[str, int]] = None,
        all_nodes: Optional[List[ContextTreeNode]] = None,
    ) -> None:
        """Apply freshly scored sibling links for a node and mirror them onto peers."""
        if all_nodes is None:
            all_nodes = await self._context_tree_repository.list_by_project(project_id)
        node_by_id = {self._node_id(n): n for n in all_nodes}
        source = node_by_id.get(str(node_id))
        if not source:
            return

        source_id = self._node_id(source)

        scored: Dict[str, int] = {}
        for peer_id, raw_score in (include_peer_scores or {}).items():
            if peer_id == source_id or peer_id not in node_by_id:
                continue
            scored[peer_id] = self._clamp_score(raw_score)

        old_source_map = self._get_link_map(source)
        new_source_map = self._merge_scores(old_source_map, scored)
        if old_source_map != new_source_map:
            await self._persist_node_fields(
                source,
                {
                    "sibling_links": self._serialize_link_map(new_source_map),
                    "updated_at": datetime.utcnow(),
                },
            )

        for other in all_nodes:
            other_id = self._node_id(other)
            if other_id == source_id or other_id not in scored:
                continue

            old_other_map = self._get_link_map(other)
            new_other_map = self._merge_scores(
                old_other_map, {source_id: scored[other_id]}
            )

            if old_other_map != new_other_map:
                await self._persist_node_fields(
                    other,
                    {
                        "sibling_links": self._serialize_link_map(new_other_map),
                        "updated_at": datetime.utcnow(),
                    },
                )

    def _to_response(self, node: ContextTreeNode) -> ContextTreeNodeResponse:
        color_val = getattr(node, "color", None)
        color = color_val if isinstance(color_val, str) else None
        conv_val = getattr(node, "conversation_id", None)
        conv = conv_val if isinstance(conv_val, str) else None

        response_links = [
            SiblingLinkPayload(
                sibling_id=link.sibling_id,
                correlation_score=self._clamp_score(link.correlation_score),
            )
            for link in self._serialize_link_map(self._get_link_map(node))
        ]

        return ContextTreeNodeResponse(
            id=self._node_id(node),
            sibling_links=response_links,
            header=getattr(node, "header", None),
            color=color,
            summary=getattr(node, "summary", None),
            topics=self._normalize_topics(getattr(node, "topics", [])),
            project_id=str(getattr(node, "project_id")),
            node_type=str(getattr(node, "node_type")),
            conversation_id=conv,
            created_at=getattr(node, "created_at"),
            updated_at=getattr(node, "updated_at"),
        )

    async def create_node(
        self, project_id: str, request: CreateContextTreeNodeRequest
    ) -> ContextTreeNodeResponse:
        """Create a node. Sibling links are set by AI organization only."""
        try:
            self._logger.debug(
                f"create_node called: project_id={project_id} request={request.dict()}"
            )
        except Exception:
            self._logger.debug(
                f"create_node called: project_id={project_id} request=<unserializable>"
            )

        request_topics = self._normalize_topics(request.topics)

        node = ContextTreeNode(
            sibling_links=[],
            header=request.header,
            summary=request.summary,
            topics=request_topics,
            project_id=project_id,
            node_type=request.node_type,
            color=request.color,
        )
        created_node = await self._context_tree_repository.create(node)
        created_node_id = self._node_id(created_node)

        req_conv = getattr(request, "conversation_id", None)
        if req_conv:
            created_node.conversation_id = req_conv
            try:
                await self._persist_node_fields(
                    created_node,
                    {
                        "conversation_id": req_conv,
                        "updated_at": datetime.utcnow(),
                    },
                )
            except Exception as e:
                self._logger.warning(
                    f"Could not persist provided conversation_id for node {created_node_id}: {e}"
                )

            try:
                import asyncio

                asyncio.create_task(
                    self._ai_organize_node(created_node, project_id, req_conv)
                )
            except Exception:
                await self._ai_organize_node(
                    created_node, project_id, req_conv, raise_on_no_response=True
                )
        else:
            conversation_id = await self._create_ai_conversation(
                created_node_id, project_id
            )
            if conversation_id:
                created_node.conversation_id = conversation_id
                try:
                    await self._persist_node_fields(
                        created_node,
                        {
                            "conversation_id": conversation_id,
                            "updated_at": datetime.utcnow(),
                        },
                    )
                except Exception as e:
                    self._logger.warning(
                        f"Could not persist conversation_id for node {created_node_id}: {e}"
                    )

                try:
                    seed_message = (
                        request.summary
                        or request.header
                        or (f"New node created with id {created_node_id}")
                    )
                    async with aiohttp.ClientSession() as session:
                        seed_url = (
                            f"{self._ai_base_url()}/ai-conversations/"
                            f"{conversation_id}/messages"
                        )
                        seed_payload = {
                            "message": seed_message,
                            "context_snapshot": {"project_id": project_id},
                        }
                        async with session.post(seed_url, json=seed_payload):
                            pass
                except Exception as e:
                    self._logger.warning(
                        f"Failed to seed AI conversation for node {created_node_id}: {e}"
                    )

                try:
                    import asyncio

                    asyncio.create_task(
                        self._ai_organize_node(
                            created_node, project_id, conversation_id
                        )
                    )
                except Exception:
                    await self._ai_organize_node(
                        created_node,
                        project_id,
                        conversation_id,
                        raise_on_no_response=True,
                    )

        refreshed = await self._context_tree_repository.get_by_id(created_node_id)
        return self._to_response(refreshed or created_node)

    async def _create_ai_conversation(
        self, context_node_id: str, project_id: str
    ) -> Optional[str]:
        """Create an AI conversation for a context node."""
        try:
            url = f"{self._ai_base_url()}/ai-conversations/"
            payload = {
                "context_node_id": context_node_id,
                "project_id": project_id,
                "title": f"AI Discussion - Node {context_node_id[:8]}",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    status = response.status
                    body = await response.text()
                    if 200 <= status < 300:
                        try:
                            return (await response.json()).get("conversation_id")
                        except Exception:
                            self._logger.error(
                                f"Failed to parse create_conversation JSON: {traceback.format_exc()}"
                            )
                            return None
                    self._logger.error(
                        f"Failed to create AI conversation: {status} - {body}"
                    )
                    return None
        except Exception as e:
            self._logger.error(
                f"Error calling AI service: {e}\n{traceback.format_exc()}"
            )
            return None

    async def _ai_organize_node(
        self,
        node: ContextTreeNode,
        project_id: str,
        conversation_id: str,
        raise_on_no_response: bool = False,
    ) -> None:
        """Request AI to analyze node metadata and sibling-link suggestions."""
        try:
            all_nodes = await self._context_tree_repository.list_by_project(project_id)
            tree_context = [
                {
                    "id": self._node_id(n),
                    "sibling_ids": sorted(self._get_link_map(n).keys()),
                    "header": n.header,
                    "summary": n.summary,
                    "topics": self._normalize_topics(getattr(n, "topics", [])),
                    "node_type": n.node_type,
                }
                for n in all_nodes
                if self._node_id(n) != self._node_id(node)
            ]

            async with aiohttp.ClientSession() as session:
                url = f"{self._ai_base_url()}/tree-analysis/organize-node"
                payload = {
                    "node_id": self._node_id(node),
                    "conversation_id": conversation_id,
                    "current_tree": tree_context,
                }
                async with session.post(url, json=payload) as response:
                    status = response.status
                    raw_body = await response.text()
                    if 200 <= status < 300:
                        try:
                            ai_suggestion = await response.json()
                        except Exception:
                            self._logger.error(
                                f"Failed to parse tree-analysis JSON: {traceback.format_exc()}"
                            )
                            ai_suggestion = {}

                        if raise_on_no_response and not ai_suggestion:
                            raise AIOrganizationError(
                                f"AI tree-analysis returned no suggestion for node {self._node_id(node)}"
                            )

                        header = str(ai_suggestion.get("header") or "").strip()
                        summary = str(ai_suggestion.get("summary") or "").strip()
                        topics = ai_suggestion.get("topics")

                        if not header:
                            raise AIOrganizationError(
                                f"AI tree-analysis missing header for node {self._node_id(node)}"
                            )
                        if not summary:
                            raise AIOrganizationError(
                                f"AI tree-analysis missing summary for node {self._node_id(node)}"
                            )
                        if not isinstance(topics, list) or not topics:
                            raise AIOrganizationError(
                                f"AI tree-analysis missing topics for node {self._node_id(node)}"
                            )

                        node.summary = summary
                        node.topics = self._normalize_topics(topics)
                        node.header = header

                        raw_scored = ai_suggestion.get("sibling_score_suggestions")
                        if not isinstance(raw_scored, list):
                            raise AIOrganizationError(
                                f"AI tree-analysis missing sibling_score_suggestions for node {self._node_id(node)}"
                            )

                        suggested_scores: Dict[str, int] = {}
                        available_ids = {
                            self._node_id(n)
                            for n in all_nodes
                            if self._node_id(n) != self._node_id(node)
                        }
                        for raw_item in raw_scored:
                            if not isinstance(raw_item, dict):
                                raise AIOrganizationError(
                                    f"AI tree-analysis sibling score entry must be an object for node {self._node_id(node)}"
                                )
                            candidate = str(raw_item.get("sibling_id") or "").strip()
                            if not candidate:
                                raise AIOrganizationError(
                                    f"AI tree-analysis sibling score entry missing sibling_id for node {self._node_id(node)}"
                                )
                            if candidate not in available_ids:
                                raise AIOrganizationError(
                                    f"AI tree-analysis returned unknown sibling_id '{candidate}' for node {self._node_id(node)}"
                                )
                            raw_score = raw_item.get("correlation_score")
                            if not isinstance(raw_score, int):
                                raise AIOrganizationError(
                                    f"AI tree-analysis sibling score must be integer for node {self._node_id(node)}"
                                )
                            suggested_scores[candidate] = self._clamp_score(raw_score)

                        await self._persist_node_fields(
                            node,
                            {
                                "header": node.header,
                                "summary": node.summary,
                                "topics": node.topics,
                                "updated_at": datetime.utcnow(),
                            },
                        )

                        await self._recompute_weighted_links_for_node(
                            project_id=project_id,
                            node_id=self._node_id(node),
                            include_peer_scores=suggested_scores,
                        )
                    else:
                        self._logger.error(
                            f"Failed to get AI organization: {response.status} - {raw_body}"
                        )
                        if raise_on_no_response:
                            raise AIOrganizationError(
                                f"AI tree-analysis failed: status={response.status} body={raw_body}"
                            )
        except Exception as e:
            self._logger.error(f"Error requesting AI organization: {e}")
            if isinstance(e, AIOrganizationError):
                raise

    async def get_node(self, node_id: str) -> Optional[ContextTreeNodeResponse]:
        node = await self._context_tree_repository.get_by_id(node_id)
        if not node:
            return None
        return self._to_response(node)

    async def list_nodes_by_project(
        self, project_id: str
    ) -> List[ContextTreeNodeResponse]:
        nodes = await self._context_tree_repository.list_by_project(project_id)
        return [self._to_response(n) for n in nodes]

    async def update_node(
        self, node_id: str, request: UpdateContextTreeNodeRequest
    ) -> Optional[ContextTreeNodeResponse]:
        """Update node metadata and keep sibling links based on AI scores only."""
        existing = await self._context_tree_repository.get_by_id(node_id)
        if not existing:
            return None

        update_data = request.dict(exclude_unset=True)

        if "topics" in update_data and update_data["topics"] is not None:
            update_data["topics"] = self._normalize_topics(update_data["topics"])

        # Link payload remains AI-owned; ignore direct manual link updates.
        update_data.pop("sibling_links", None)

        update_data["updated_at"] = datetime.utcnow()
        node = await self._context_tree_repository.update(node_id, update_data)
        if not node:
            return None

        await self._recompute_weighted_links_for_node(
            project_id=str(getattr(node, "project_id")),
            node_id=str(node_id),
            include_peer_scores=self._get_link_map(node),
        )

        refreshed = await self._context_tree_repository.get_by_id(str(node_id))
        return self._to_response(refreshed or node)

    async def apply_sibling_scores(
        self,
        node_id: str,
        scores: List[SiblingScorePayload],
        source: str = "embedding",
    ) -> Optional[ContextTreeNodeResponse]:
        """Apply externally computed sibling scores and mirror them onto peers."""
        node = await self._context_tree_repository.get_by_id(node_id)
        if not node:
            return None

        node_id_str = str(node_id)
        project_id = str(getattr(node, "project_id"))
        all_nodes = await self._context_tree_repository.list_by_project(project_id)
        known_ids = {self._node_id(n) for n in all_nodes}

        unknown_ids = sorted({s.sibling_id for s in scores}.difference(known_ids))
        if unknown_ids:
            raise UnknownSiblingError(
                f"Unknown sibling ids for node {node_id_str}: {unknown_ids[:5]}"
            )

        self._logger.info(
            f"Applying {len(scores)} sibling scores to node {node_id_str} from {source}"
        )
        await self._recompute_weighted_links_for_node(
            project_id=project_id,
            node_id=node_id_str,
            include_peer_scores={s.sibling_id: s.correlation_score for s in scores},
            all_nodes=all_nodes,
        )

        refreshed = await self._context_tree_repository.get_by_id(node_id_str)
        return self._to_response(refreshed or node)

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and clean reciprocal sibling links from other nodes."""
        self._logger.info(f"Attempting to delete node {node_id}")
        node = await self._context_tree_repository.get_by_id(node_id)
        if not node:
            self._logger.warning(f"Node {node_id} not found for deletion")
            return False

        node_id_str = str(node_id)
        all_nodes = await self._context_tree_repository.list_by_project(
            str(getattr(node, "project_id"))
        )

        for sibling in all_nodes:
            sibling_id = self._node_id(sibling)
            if sibling_id == node_id_str:
                continue
            sibling_map = self._get_link_map(sibling)
            if node_id_str not in sibling_map:
                continue
            sibling_map.pop(node_id_str, None)
            await self._persist_node_fields(
                sibling,
                {
                    "sibling_links": self._serialize_link_map(sibling_map),
                    "updated_at": datetime.utcnow(),
                },
            )

        conv_id = getattr(node, "conversation_id", None)
        if conv_id:
            try:
                await self._delete_ai_conversation(conv_id)
            except Exception as e:
                self._logger.error(f"Failed to delete AI conversation {conv_id}: {e}")

        deleted = await self._context_tree_repository.delete(node_id)
        if deleted:
            self._logger.info(f"Node {node_id} deleted successfully")
        else:
            self._logger.error(f"Failed to delete node {node_id} from repository")
        return deleted

    async def _delete_ai_conversation(self, conversation_id: str) -> bool:
        """Request AI service to delete a conversation by id."""
        try:
            url = f"{self._ai_base_url()}/ai-conversations/{conversation_id}"
            async with aiohttp.ClientSession() as session:
                async with session.delete(url) as response:
                    status = response.status
                    body = await response.text()
                    if 200 <= status < 300:
                        return True
                    self._logger.error(f"AI delete returned {status}: {body}")
                    return False
        except Exception as e:
            self._logger.error(
                f"Error deleting AI conversation: {e}\n{traceback.format_exc()}"
            )
            return False
