from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime


class SiblingLinkPayload(BaseModel):
    sibling_id: str
    correlation_score: int = Field(default=0, ge=0, le=100)


class SiblingScorePayload(BaseModel):
    sibling_id: str
    correlation_score: int = Field(ge=0, le=100)


class UpdateSiblingScoresRequest(BaseModel):
    scores: list[SiblingScorePayload] = Field(default_factory=list)
    source: Literal["embedding", "manual"] = "embedding"


class CreateContextTreeNodeRequest(BaseModel):
    sibling_links: List[SiblingLinkPayload] = Field(default_factory=list)
    header: Optional[str] = None
    summary: Optional[str] = None
    conversation_id: Optional[str] = None
    messages: Optional[List[dict]] = None
    topics: List[str] = Field(default_factory=list)
    node_type: str = "goal"
    color: Optional[str] = None


class UpdateContextTreeNodeRequest(BaseModel):
    sibling_links: Optional[List[SiblingLinkPayload]] = None
    header: Optional[str] = None
    summary: Optional[str] = None
    topics: Optional[List[str]] = None
    node_type: Optional[str] = None
    color: Optional[str] = None


class ContextTreeNodeResponse(BaseModel):
    id: str
    sibling_links: List[SiblingLinkPayload]
    header: Optional[str]
    color: Optional[str] = None
    summary: Optional[str]
    topics: List[str]
    project_id: str
    node_type: str
    conversation_id: Optional[str]
    created_at: datetime
    updated_at: datetime
