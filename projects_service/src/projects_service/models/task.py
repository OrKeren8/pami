from beanie import Document
from typing import List, Optional
from datetime import datetime
from pydantic import Field


class Task(Document):
    title: str
    description: Optional[str] = None
    status: str  # e.g., "todo", "in-progress", "done"
    due_date: Optional[datetime] = None
    assignee: Optional[str] = None  # user ID
    dependencies: List[str] = Field(default_factory=list)  # list of task IDs
    project_id: str  # reference to project
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "tasks"
