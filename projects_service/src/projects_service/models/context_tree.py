from beanie import Document
from typing import List, Optional
from datetime import datetime


class ContextTreeNode(Document):
    node_id: str  # unique identifier
    parent_id: Optional[str] = None
    children_ids: List[str] = []
    text: str  # short text about what the node is about
    project_id: str  # reference to project
    node_type: str  # e.g., "goal", "task", "milestone"
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    class Settings:
        name = "context_tree"
