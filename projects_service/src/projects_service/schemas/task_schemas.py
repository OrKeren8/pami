from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "todo"
    due_date: Optional[datetime] = None
    assignee: Optional[str] = None
    dependencies: List[str] = []


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    assignee: Optional[str] = None
    dependencies: Optional[List[str]] = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    due_date: Optional[datetime]
    assignee: Optional[str]
    dependencies: List[str]
    project_id: str
    created_at: datetime
    updated_at: datetime
