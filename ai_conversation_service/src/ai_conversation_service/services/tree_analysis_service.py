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

        # Build tree context description
        tree_context = self._build_tree_context(request.current_tree)
        
        # Get conversation messages
        conversation_history = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in conversation.messages[-10:]]
        )

        # Create AI prompt
        system_prompt = """You are an expert project management AI that organizes project nodes into a hierarchical tree structure.

Your task:
1. Read the conversation about a project node
2. Analyze the existing project tree structure
3. Determine the best parent for this node based on:
   - Content and purpose discussed in the conversation
   - Logical hierarchy (goals > tasks > subtasks)
   - Thematic similarity with existing nodes
4. Generate a clear summary of the node
5. Extract relevant topics/tags

Return your analysis as JSON with:
- suggested_parent_id: The ID of the best parent node (or null for root-level)
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
            response = await self._openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent analysis
            )

            # Parse AI response
            ai_response = json.loads(response.choices[0].message.content)
            
            return NodeOrganizationResponse(
                node_id=request.node_id,
                suggested_parent_id=ai_response.get("suggested_parent_id"),
                summary=ai_response.get("summary", ""),
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
        summary_preview = (node.summary[:50] + "...") if node.summary and len(node.summary) > 50 else (node.summary or "")
        topics_str = f" [{', '.join(node.topics)}]" if node.topics else ""
        
        lines.append(
            f"{indent}- [{node.node_type}] {node.id[:8]}... : {node.text[:60]}{topics_str}"
        )
        if summary_preview:
            lines.append(f"{indent}  Summary: {summary_preview}")
        
        # Find and add children
        children = [n for n in node_map.values() if n.parent_id == node.id]
        for child in children:
            self._add_node_to_tree(child, node_map, lines, level + 1)
