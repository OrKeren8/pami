from beanie import Document, PydanticObjectId
from typing import List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel


class SiblingLink(BaseModel):
    sibling_id: str
    correlation_score: int = Field(default=0, ge=0, le=100)


class ContextTreeNode(Document):
    # Accept both ObjectId (PydanticObjectId) and legacy string IDs (UUIDs)
    id: Optional[Union[PydanticObjectId, str]] = None
    sibling_links: List[SiblingLink] = Field(default_factory=list)
    # `header` is a short title chosen by AI (5 words max, prefer 2-3)
    header: Optional[str] = None
    summary: Optional[str] = (
        None  # Summary of conversation or content (up to ~3 sentences)
    )
    topics: List[str] = Field(default_factory=list)  # Topics for indexing and parsing
    project_id: str  # reference to project (kept as str for backward compatibility)
    node_type: str  # e.g., "goal", "task", "milestone"
    color: Optional[str] = None
    conversation_id: Optional[str] = None  # Link to AI conversation
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "context_tree"
        # Listing a project's nodes was a full collection scan, and it runs on every node
        # fetch, create, update, score push and delete - several of those twice per request.
        # Cost grew with the total node count across all projects, not with the project's own.
        indexes = [
            IndexModel([("project_id", ASCENDING)], name="project"),
            IndexModel([("conversation_id", ASCENDING)], name="conversation"),
        ]
