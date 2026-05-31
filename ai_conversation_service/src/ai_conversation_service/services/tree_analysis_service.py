from typing import Optional
from loguru import logger
from openai import AsyncOpenAI
import json

from ai_conversation_service.schemas.tree_analysis_schemas import (
    AnalyzeTreeRequest,
    NodeOrganizationResponse,
    TreeNodeData,
)
from ai_conversation_service.core.config import settings
import re

# Patterns considered overly generic for headers (lowercase, partial match)
_GENERIC_HEADER_PATTERNS = [
    r"^an informative overview$",
    r"^an informative overview about",
    r"^an overview$",
    r"^an overview about",
    r"^summary",
    r"^an informative summary",
    r"^introduction",
]

_STOPWORDS = {
    "about",
    "the",
    "and",
    "of",
    "an",
    "a",
    "to",
    "for",
    "in",
    "on",
    "with",
    "by",
    "from",
}


class TreeAnalysisService:
    """Service for AI-powered tree organization and node placement."""

    def __init__(
        self,
        ai_conversation_service,  # Reference to AIConversationService
        openai_client: AsyncOpenAI,
    ):
        self._logger = logger.bind(service="TreeAnalysisService")
        self._ai_conversation_service = ai_conversation_service
        self._openai_client = openai_client

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

        # Build tree context description
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

        # Create AI prompt
        system_prompt = """You are an expert project management AI that organizes project nodes into a hierarchical tree structure.

Your task:
1. Read the conversation about a project node
2. Analyze the existing project tree structure
3. Determine the best parent for this node based on:
   - Content and purpose discussed in the conversation
   - Logical hierarchy (goals > tasks > subtasks)
   - Thematic similarity with existing nodes
4. Generate a clear summary of the node (1-3 sentences)
5. Extract relevant topics/tags
6. Propose a concise header (title) for the node: *exactly* 3 to 5 words, focus on the concrete subject/topic (e.g., use "Birds overview" not "An Informative Overview").
   - Prefer noun phrases and specific domain words (e.g., "Birds overview", "User auth flow", "Data ingestion pipeline").
   - Avoid generic lead-in phrases like "An Informative Overview", "Summary of", "Overview of", "Introduction to".
   - If multiple concise options exist, pick the most specific and informative.

Return your analysis as JSON with these fields (use null for missing ids):
- suggested_parent_id: The ID of the best parent node (or null for root-level)
- header: A concise title (3-5 words)
- summary: A concise summary of what this node is about
- topics: Array of relevant topic tags
- reasoning: Brief explanation of your placement decision"""

        user_prompt = f"""Analyze this new project node and suggest its organization:

NODE ID: {request.node_id}

CONVERSATION ABOUT THIS NODE:
{conversation_history}

CURRENT PROJECT TREE:
{tree_context}

Suggest where this node should be placed in the tree, provide a summary, extract topics, and explain your reasoning."""

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
                self._logger.debug(f"Raw model output (truncated): {raw_output[:2000]}")
            except Exception:
                self._logger.debug("Raw model output: <unserializable>")

            # Parse AI response
            ai_response = json.loads(response.choices[0].message.content)

            header = ai_response.get("header")
            summary = ai_response.get("summary", "")

            # Fallback heuristics: if model returns a missing or overly generic header,
            # synthesize a concise, concrete 3-5 word header from the summary or conversation.
            if not header or self._is_generic_header(header):
                header = self._generate_header(conversation_history, summary)

            return NodeOrganizationResponse(
                node_id=request.node_id,
                suggested_parent_id=ai_response.get("suggested_parent_id"),
                header=header,
                summary=summary,
                topics=ai_response.get("topics", []),
                reasoning=ai_response.get("reasoning", ""),
            )

        except Exception as e:
            self._logger.error(f"Failed to analyze tree structure: {e}")
            raise

    def _build_tree_context(self, nodes: list[TreeNodeData]) -> str:
        """Build a readable tree context for AI analysis."""
        if not nodes:
            return "Empty tree - this will be the first node."

        # Build tree structure representation
        tree_lines = ["Project Tree Structure:"]
        tree_lines.append("=" * 50)

        # Create a map of nodes by ID
        node_map = {node.id: node for node in nodes}

        # Find root nodes (no parent)
        root_nodes = [node for node in nodes if not node.parent_id]

        # Build tree representation recursively
        for root in root_nodes:
            self._add_node_to_tree(root, node_map, tree_lines, level=0)

        return "\n".join(tree_lines)

    def _add_node_to_tree(
        self,
        node: TreeNodeData,
        node_map: dict,
        lines: list,
        level: int,
    ):
        """Recursively add node and children to tree representation."""
        indent = "  " * level
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

        lines.append(
            f"{indent}- [{node.node_type}] {node.id[:8]}... : {header_preview}{topics_str}"
        )
        if summary_preview:
            lines.append(f"{indent}  Summary: {summary_preview}")

        # Find and add children
        children = [n for n in node_map.values() if n.parent_id == node.id]
        for child in children:
            self._add_node_to_tree(child, node_map, lines, level + 1)

    def _is_generic_header(self, header: Optional[str]) -> bool:
        """Return True if the header looks generic or uninformative."""
        if not header:
            return True
        h = re.sub(r"[^a-z0-9 ]", "", header.lower()).strip()
        for p in _GENERIC_HEADER_PATTERNS:
            if re.search(p, h):
                return True
        # If header contains one of these generic tokens and is short, treat as generic
        if any(
            tok in h for tok in ("overview", "informative", "summary", "introduction")
        ):
            if len(h.split()) <= 4:
                return True
        return False

    def _generate_header(self, conversation_history: str, summary: str) -> str:
        """Generate a 3-5 word concise header from summary or conversation text.

        Strategy:
        - Prefer to extract noun-phrases by simple heuristics: pick meaningful words,
          drop stopwords, preserve original order, and title-case the result.
        - Ensure result has at least 3 words; if not, append most common domain words.
        - Limit to 5 words.
        """
        text = ((summary or "") + " " + (conversation_history or "")).strip()
        # remove role prefixes and punctuation
        text = re.sub(r"\b(user|assistant|system):", "", text, flags=re.I)
        # Tokenize into words
        words = re.findall(r"[A-Za-z0-9]+", text)
        # Filter short words and stopwords
        words = [w for w in words if len(w) > 2 and w.lower() not in _STOPWORDS]
        if not words:
            return "Miscellaneous Topic"

        # Preserve first occurrences up to 5 meaningful words
        selected = []
        seen = set()
        for w in words:
            lw = w.lower()
            if lw in seen:
                continue
            seen.add(lw)
            selected.append(w)
            if len(selected) >= 5:
                break

        header = " ".join(selected[:5]).title()

        # If too short (<3 words), append most common words from text
        if len(header.split()) < 3:
            from collections import Counter

            ctr = Counter([w.lower() for w in words])
            most = [w for w, _ in ctr.most_common() if w not in _STOPWORDS]
            for w in most:
                if w.title() not in header:
                    header = (header + " " + w.title()).strip()
                if len(header.split()) >= 3:
                    break

        # Ensure max 5 words
        header = " ".join(header.split()[:5])
        return header
