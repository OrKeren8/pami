from beanie import Document
from typing import List, Optional
from datetime import datetime
import uuid
from pydantic import Field


class ContextTreeNode(Document):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    children_ids: List[str] = []
    text: str  # Can store up to ~4 million characters (16MB limit)
    summary: Optional[str] = None  # Summary of conversation or content
    topics: List[str] = []  # Topics for indexing and parsing
    project_id: str  # reference to project
    node_type: str  # e.g., "goal", "task", "milestone"
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    class Settings:
        name = "context_tree"
