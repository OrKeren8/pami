from loguru import logger
from openai import AsyncOpenAI
import json

from ai_conversation_service.schemas.tree_analysis_schemas import (
    AnalyzeTreeRequest,
    NodeOrganizationResponse,
    SiblingScoreSuggestion,
    TreeNodeData,
)
from ai_conversation_service.core.config import settings
from ai_conversation_service.core.prompt_loader import load_prompt_file
from ai_conversation_service.services.similarity import top_k_scores

TREE_ANALYSIS_SYSTEM_PROMPT = load_prompt_file("tree_analysis_system_prompt.txt")
TREE_ANALYSIS_USER_PROMPT_TEMPLATE = load_prompt_file("tree_analysis_user_prompt.txt")


class TreeAnalysisService:
    """Service for AI-powered tree organization and node placement."""

    def __init__(
        self,
        ai_conversation_service,  # Reference to AIConversationService
        openai_client: AsyncOpenAI,
        chunk_index_service,
    ):
        self._logger = logger.bind(service="TreeAnalysisService")
        self._ai_conversation_service = ai_conversation_service
        self._openai_client = openai_client
        self._chunk_index_service = chunk_index_service

    async def analyze_and_organize_node(
        self, request: AnalyzeTreeRequest
    ) -> NodeOrganizationResponse:
        """Analyze conversation and tree to suggest optimal node organization."""

        # Get conversation history
        conversation = await self._ai_conversation_service.get_conversation(
            request.conversation_id
        )

        if not conversation:
            raise ValueError(f"Conversation {request.conversation_id} not found")

        # Log conversation metadata for debugging
        try:
            msg_count = len(conversation.messages or [])
        except Exception:
            msg_count = -1
        self._logger.debug(
            f"analyze_and_organize_node: conversation_id={request.conversation_id} messages={msg_count}"
        )

        # Build graph context description
        tree_context = self._build_tree_context(request.current_tree)

        # Get conversation messages
        conversation_history = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in conversation.messages[-10:]]
        )
        # Log a truncated conversation history for traceability
        try:
            self._logger.debug(
                f"conversation_history (last {min(10, msg_count)}): {conversation_history[:1000]}"
            )
        except Exception:
            self._logger.debug("conversation_history: <unserializable>")

        # Create AI prompts from external prompt files.
        system_prompt = TREE_ANALYSIS_SYSTEM_PROMPT
        user_prompt = TREE_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            node_id=request.node_id,
            conversation_history=conversation_history,
            tree_context=tree_context,
        )

        try:
            # Call OpenAI
            self._logger.debug(
                f"Sending prompts to model={settings.openai_model} system_prompt_len={len(system_prompt)} user_prompt_len={len(user_prompt)}"
            )
            response = await self._openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent analysis
            )

            # Log raw model output for debugging
            try:
                raw_output = response.choices[0].message.content
                self._logger.debug(
                    f"Raw model output (truncated): {(raw_output or '')[:2000]}"
                )
            except Exception:
                self._logger.debug("Raw model output: <unserializable>")

            # Parse AI response
            raw_content = response.choices[0].message.content or "{}"
            ai_response = json.loads(raw_content)

            header = str(ai_response.get("header") or "").strip()
            summary = str(ai_response.get("summary") or "").strip()
            topics = ai_response.get("topics")

            if not header:
                raise ValueError("AI organization missing required field: header")
            header_word_count = len(header.split())
            if header_word_count < 3 or header_word_count > 5:
                raise ValueError(
                    f"AI organization header must contain 3-5 words, got {header_word_count}: '{header}'"
                )

            if not summary or len(summary) < 40:
                raise ValueError(
                    "AI organization summary is missing or too short (minimum 40 chars required)"
                )

            if not isinstance(topics, list) or not topics:
                raise ValueError("AI organization missing required non-empty topics")

            scored_suggestions = await self._score_siblings(request)

            return NodeOrganizationResponse(
                node_id=request.node_id,
                sibling_score_suggestions=scored_suggestions,
                header=header,
                summary=summary,
                topics=topics,
                reasoning=ai_response.get("reasoning", ""),
            )

        except Exception as e:
            self._logger.error(f"Failed to analyze tree structure: {e}")
            raise

    async def _score_siblings(
        self, request: AnalyzeTreeRequest
    ) -> list[SiblingScoreSuggestion]:
        """Score siblings by embedding cosine similarity."""
        if not self._chunk_index_service:
            self._logger.warning(
                "Chunk index unavailable; returning no sibling scores for node "
                f"{request.node_id}"
            )
            return []

        state = await self._chunk_index_service.state_for(request.conversation_id)
        if not state:
            return []

        similarities = await self._chunk_index_service.conversation_similarities(
            state.project_id, request.conversation_id
        )
        known_node_ids = {str(node.id) for node in request.current_tree}
        candidates = {
            node_id: similarity
            for node_id, similarity in similarities.items()
            if node_id in known_node_ids
        }

        scores = top_k_scores(candidates, state.embedding_model, settings.sibling_top_k)
        self._logger.info(
            f"Scored {len(scores)} of {len(known_node_ids)} peers for node "
            f"{request.node_id} by cosine"
        )
        return [
            SiblingScoreSuggestion(sibling_id=node_id, correlation_score=score)
            for node_id, score in scores.items()
        ]

    def _build_tree_context(self, nodes: list[TreeNodeData]) -> str:
        """Build a readable graph context for AI analysis."""
        if not nodes:
            return "Empty graph - this will be the first node."

        lines = ["Project Node Graph:"]
        lines.append("=" * 50)

        for node in nodes:
            summary_preview = (
                (node.summary[:50] + "...")
                if node.summary and len(node.summary) > 50
                else (node.summary or "")
            )
            topics_str = f" [{', '.join(node.topics)}]" if node.topics else ""
            header_preview = (
                (node.header[:60] + "...")
                if node.header and len(node.header) > 60
                else (node.header or "")
            )
            siblings_preview = ", ".join(node.sibling_ids[:6])
            if len(node.sibling_ids) > 6:
                siblings_preview += ", ..."
            lines.append(
                f"- [{node.node_type}] {node.id} : {header_preview}{topics_str}"
            )
            if summary_preview:
                lines.append(f"  Summary: {summary_preview}")
            lines.append(
                f"  Siblings: {siblings_preview if siblings_preview else 'none'}"
            )

        return "\n".join(lines)
