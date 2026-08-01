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
    """One other conversation whose text reached the model on this turn.

    `read` separates the two very different levels of access: a search hit puts one
    window in front of the model, while read_conversation pulls a wide span of the
    transcript. Reporting both as simply "consulted" overstated the first.
    """

    conversation_id: str
    header: str | None = None
    hit_count: int = 0
    best_score: float = 0.0
    read: bool = False


class SearchContextRequest(BaseModel):
    project_id: str
    query: str
    limit: int = Field(default=5, ge=1, le=20)
    exclude_conversation_id: str | None = None


class SendMessageResult(BaseModel):
    response: str
    consulted: list[ConsultedConversation] = Field(default_factory=list)
    tool_calls_used: int = 0
