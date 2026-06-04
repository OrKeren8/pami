from typing import Dict, Iterable, List, Optional, Set
from datetime import datetime
from loguru import logger
import aiohttp
import re
import traceback
from difflib import SequenceMatcher

from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.models.context_tree import ContextTreeNode, SiblingLink
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
    SiblingLinkPayload,
)
from projects_service.core.config import settings


class AIOrganizationError(Exception):
    """Raised when the AI organization service fails to provide a usable response."""


class ContextTreeService:
    """Service for sibling-link graph business logic based on summary similarity."""

    _MIN_CORRELATION_SCORE = 30
    _MIN_SUMMARY_CHAR_LEN = 30
    _MIN_SUMMARY_TOKEN_COUNT = 5

    _TOPIC_STOPWORDS = {
        "about",
        "also",
        "and",
        "are",
        "been",
        "between",
        "for",
        "from",
        "have",
        "just",
        "like",
        "more",
        "node",
        "project",
        "that",
        "the",
        "this",
        "with",
        "your",
    }

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

    def _summary_tokens(self, text: Optional[str]) -> List[str]:
        if not text:
            return []
        return re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text.lower())

    def _has_meaningful_summary(self, text: Optional[str]) -> bool:
        if not text:
            return False
        if len(text.strip()) < self._MIN_SUMMARY_CHAR_LEN:
            return False
        return len(self._summary_tokens(text)) >= self._MIN_SUMMARY_TOKEN_COUNT

    def _summary_similarity_score(
        self,
        left_summary: Optional[str],
        right_summary: Optional[str],
    ) -> int:
        if not self._has_meaningful_summary(left_summary):
            return 0
        if not self._has_meaningful_summary(right_summary):
            return 0

        left_tokens = [
            t
            for t in self._summary_tokens(left_summary)
            if t not in self._TOPIC_STOPWORDS
        ]
        right_tokens = [
            t
            for t in self._summary_tokens(right_summary)
            if t not in self._TOPIC_STOPWORDS
        ]
        if not left_tokens or not right_tokens:
            return 0

        left_set = set(left_tokens)
        right_set = set(right_tokens)
        union = left_set.union(right_set)
        if not union:
            return 0

        token_jaccard = len(left_set.intersection(right_set)) / len(union)

        left_bigrams = set(zip(left_tokens, left_tokens[1:]))
        right_bigrams = set(zip(right_tokens, right_tokens[1:]))
        if left_bigrams and right_bigrams:
            bigram_union = left_bigrams.union(right_bigrams)
            bigram_overlap = (
                len(left_bigrams.intersection(right_bigrams)) / len(bigram_union)
                if bigram_union
                else 0.0
            )
        else:
            bigram_overlap = 0.0

        sequence_ratio = SequenceMatcher(
            None,
            " ".join(left_tokens),
            " ".join(right_tokens),
        ).ratio()

        weighted = (
            (token_jaccard * 0.55) + (bigram_overlap * 0.25) + (sequence_ratio * 0.20)
        )
        return self._clamp_score(round(weighted * 100))

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

    def _infer_topics(
        self,
        header: Optional[str],
        summary: Optional[str],
        messages: Optional[List[dict]],
    ) -> List[str]:
        """Fallback tag extraction when explicit/AI topics are not yet available."""
        text_parts: List[str] = []
        if header:
            text_parts.append(header)
        if summary:
            text_parts.append(summary)
        for msg in messages or []:
            content = msg.get("content") if isinstance(msg, dict) else None
            if content:
                text_parts.append(str(content))

        tokens = re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", " ".join(text_parts).lower())
        inferred: List[str] = []
        seen = set()
        for token in tokens:
            if token in self._TOPIC_STOPWORDS:
                continue
            if token in seen:
                continue
            seen.add(token)
            inferred.append(token)
            if len(inferred) >= 10:
                break
        return inferred

    def _get_link_map(self, node: ContextTreeNode) -> Dict[str, int]:
        link_map: Dict[str, int] = {}
        for link in getattr(node, "sibling_links", []) or []:
            sibling_id = str(getattr(link, "sibling_id", "")).strip()
            if not sibling_id:
                continue
            score = getattr(link, "correlation_score", None)
            if score is None and isinstance(link, dict):
                score = link.get("correlation_score")

            # Backward compatibility for old docs persisted as shared_tags.
            if score is None:
                tags = getattr(link, "shared_tags", None)
                if tags is None and isinstance(link, dict):
                    tags = link.get("shared_tags")
                if isinstance(tags, list):
                    score = min(100, len(tags) * 20)

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
        try:
            for key, val in fields.items():
                setattr(node, key, val)
            await node.save()
        except TypeError:
            await self._context_tree_repository.update(self._node_id(node), fields)

    async def _recompute_weighted_links_for_node(
        self,
        project_id: str,
        node_id: str,
    ) -> None:
        """Recompute sibling links from summary correlation and enforce symmetry."""
        all_nodes = await self._context_tree_repository.list_by_project(project_id)
        node_by_id = {self._node_id(n): n for n in all_nodes}
        source = node_by_id.get(str(node_id))
        if not source:
            return

        source_id = self._node_id(source)
        source_summary = getattr(source, "summary", None)

        desired_source_map: Dict[str, int] = {}
        for other in all_nodes:
            other_id = self._node_id(other)
            if other_id == source_id:
                continue
            score = self._summary_similarity_score(
                source_summary,
                getattr(other, "summary", None),
            )
            if score >= self._MIN_CORRELATION_SCORE:
                desired_source_map[other_id] = score

        old_source_map = self._get_link_map(source)
        if old_source_map != desired_source_map:
            await self._persist_node_fields(
                source,
                {
                    "sibling_links": self._serialize_link_map(desired_source_map),
                    "updated_at": datetime.utcnow(),
                },
            )

        for other in all_nodes:
            other_id = self._node_id(other)
            if other_id == source_id:
                continue

            old_other_map = self._get_link_map(other)
            new_other_map = dict(old_other_map)

            if other_id in desired_source_map:
                new_other_map[source_id] = desired_source_map[other_id]
            else:
                new_other_map.pop(source_id, None)

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
        """Create a node and compute sibling links by summary correlation."""
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

        # Compute initial sibling links from summary correlation.
        await self._recompute_weighted_links_for_node(
            project_id=project_id,
            node_id=created_node_id,
        )

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

                        node.summary = ai_suggestion.get("summary", node.summary)
                        node.topics = self._normalize_topics(
                            ai_suggestion.get("topics", node.topics)
                        )
                        node.header = ai_suggestion.get("header", node.header)

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
        """Update node metadata and recompute sibling links by summary correlation."""
        existing = await self._context_tree_repository.get_by_id(node_id)
        if not existing:
            return None

        update_data = request.dict(exclude_unset=True)

        if "topics" in update_data and update_data["topics"] is not None:
            update_data["topics"] = self._normalize_topics(update_data["topics"])

        # Link weights are derived from summary correlation; direct link payload is not persisted verbatim.
        update_data.pop("sibling_links", None)

        update_data["updated_at"] = datetime.utcnow()
        node = await self._context_tree_repository.update(node_id, update_data)
        if not node:
            return None

        await self._recompute_weighted_links_for_node(
            project_id=str(getattr(node, "project_id")),
            node_id=str(node_id),
        )

        refreshed = await self._context_tree_repository.get_by_id(str(node_id))
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
