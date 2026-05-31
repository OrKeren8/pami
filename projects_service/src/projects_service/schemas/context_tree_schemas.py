from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CreateContextTreeNodeRequest(BaseModel):
    parent_id: Optional[str] = None
    children_ids: List[str] = []
    text: str
    summary: Optional[str] = None
    topics: List[str] = []
    node_type: str = "goal"
    color: Optional[str] = None


class UpdateContextTreeNodeRequest(BaseModel):
    parent_id: Optional[str] = None
    children_ids: Optional[List[str]] = None
    text: Optional[str] = None
    summary: Optional[str] = None
    topics: Optional[List[str]] = None
    node_type: Optional[str] = None
    color: Optional[str] = None


class ContextTreeNodeResponse(BaseModel):
    id: str
    parent_id: Optional[str]
    children_ids: List[str]
    text: str
    color: Optional[str] = None
    summary: Optional[str]
    topics: List[str]
    project_id: str
    node_type: str
    conversation_id: Optional[str]
    created_at: datetime
    updated_at: datetime
