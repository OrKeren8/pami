from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CreateContextTreeNodeRequest(BaseModel):
    parent_id: Optional[str] = None
    children_ids: List[str] = []
    text: str
    node_type: str = "goal"


class UpdateContextTreeNodeRequest(BaseModel):
    parent_id: Optional[str] = None
    children_ids: Optional[List[str]] = None
    text: Optional[str] = None
    node_type: Optional[str] = None


class ContextTreeNodeResponse(BaseModel):
    id: str
    parent_id: Optional[str]
    children_ids: List[str]
    text: str
    project_id: str
    node_type: str
    created_at: datetime
    updated_at: datetime
