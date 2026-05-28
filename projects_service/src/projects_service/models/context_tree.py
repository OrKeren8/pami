from beanie import Document, PydanticObjectId
from typing import List, Optional, Union
from datetime import datetime


class ContextTreeNode(Document):
    # Accept both ObjectId (PydanticObjectId) and legacy string IDs (UUIDs)
    id: Optional[Union[PydanticObjectId, str]] = None
    parent_id: Optional[str] = None
    children_ids: List[str] = []
    text: str  # Can store up to ~4 million characters (16MB limit)
    summary: Optional[str] = None  # Summary of conversation or content
    topics: List[str] = []  # Topics for indexing and parsing
    project_id: str  # reference to project (kept as str for backward compatibility)
    node_type: str  # e.g., "goal", "task", "milestone"
    conversation_id: Optional[str] = None  # Link to AI conversation
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    class Settings:
        name = "context_tree"
