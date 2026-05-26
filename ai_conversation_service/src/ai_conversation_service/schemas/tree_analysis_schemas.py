from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class TreeNodeData(BaseModel):
    """Simplified node data for tree analysis."""
    id: str
    parent_id: Optional[str]
    text: str
    summary: Optional[str]
    topics: List[str]
    node_type: str


class AnalyzeTreeRequest(BaseModel):
    """Request to analyze and organize a node in the project tree."""
    node_id: str
    conversation_id: str
    current_tree: List[TreeNodeData]  # All nodes in the project


class NodeOrganizationResponse(BaseModel):
    """AI's recommendation for node organization and metadata."""
    node_id: str
    suggested_parent_id: Optional[str]
    summary: str
    topics: List[str]
    reasoning: str  # AI explanation for the placement
