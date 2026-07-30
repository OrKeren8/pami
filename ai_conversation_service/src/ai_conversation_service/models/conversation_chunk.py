from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class ConversationChunk(Document):
    """A rolling window of conversation messages, embedded for retrieval."""

    conversation_id: str
    node_id: str | None = None
    project_id: str
    text: str
    message_start: int
    message_end: int
    embedding: list[float]
    embedding_model: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "conversation_chunks"
        indexes = [
            IndexModel(
                [("conversation_id", ASCENDING), ("message_start", ASCENDING)],
                unique=True,
                name="conversation_message_window_unique",
            ),
            IndexModel(
                [("project_id", ASCENDING), ("conversation_id", ASCENDING)],
                name="project_conversation",
            ),
        ]
