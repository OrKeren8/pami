from beanie import Document
from typing import List, Optional
from datetime import datetime
from pydantic import Field
from pymongo import ASCENDING, IndexModel


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
        # Tasks are always fetched per project; without this the lookup scans every task in
        # the database.
        indexes = [IndexModel([("project_id", ASCENDING)], name="project")]
