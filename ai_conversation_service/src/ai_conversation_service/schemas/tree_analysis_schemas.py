from typing import List, Optional

from pydantic import BaseModel, Field


class TreeNodeData(BaseModel):
    id: str
    sibling_ids: List[str] = Field(default_factory=list)
    header: Optional[str] = None
    summary: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    node_type: str = "goal"


class AnalyzeTreeRequest(BaseModel):
    node_id: str
    conversation_id: str
    current_tree: List[TreeNodeData] = Field(default_factory=list)


class NodeOrganizationResponse(BaseModel):
    node_id: str
    suggested_sibling_ids: List[str] = Field(default_factory=list)
    header: Optional[str] = None
    summary: str
    topics: List[str] = Field(default_factory=list)
    reasoning: str
