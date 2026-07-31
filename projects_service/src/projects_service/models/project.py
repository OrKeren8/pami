from beanie import Document
from typing import Optional
from datetime import datetime
from pydantic import Field
from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on-hold"


class Project(Document):
    name: str
    goal: str
    status: ProjectStatus  # e.g., "active", "completed", "on-hold"
    color: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "projects"
