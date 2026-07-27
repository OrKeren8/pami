from typing import Literal

from pydantic import BaseModel, Field


class ContextHit(BaseModel):
    conversation_id: str
    node_id: str | None = None
    header: str | None = None
    snippet: str
    score: float = Field(ge=-1.0, le=1.0)
    via: Literal["vector", "graph_expansion"] = "vector"


class ConsultedConversation(BaseModel):
    conversation_id: str
    header: str | None = None
    hit_count: int = 0


class SearchContextRequest(BaseModel):
    project_id: str
    query: str
    limit: int = Field(default=5, ge=1, le=20)
    exclude_conversation_id: str | None = None


class SendMessageResult(BaseModel):
    response: str
    consulted: list[ConsultedConversation] = Field(default_factory=list)
    tool_calls_used: int = 0
