from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class ConversationIndexState(Document):
    """Per-conversation indexing bookkeeping and its graph-scoring vector."""

    conversation_id: str
    node_id: str | None = None
    project_id: str
    header: str | None = None
    embedding: list[float] = Field(default_factory=list)
    embedding_model: str = ""
    last_indexed_message_index: int = -1
    message_count_at_index: int = 0
    last_scored_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "conversation_index_state"
        indexes = [
            IndexModel(
                [("conversation_id", ASCENDING)],
                unique=True,
                name="conversation_id_unique",
            ),
            IndexModel([("project_id", ASCENDING)], name="project"),
            IndexModel(
                [("project_id", ASCENDING), ("node_id", ASCENDING)],
                name="project_node",
            ),
        ]
