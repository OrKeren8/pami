from beanie import Document
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId


class Task(Document):
    title: str
    description: Optional[str] = None
    status: str  # e.g., "todo", "in-progress", "done"
    due_date: Optional[datetime] = None
    assignee: Optional[str] = None  # user ID
    dependencies: List[str] = []  # list of task IDs
    project_id: str  # reference to project
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    class Settings:
        name = "tasks"
