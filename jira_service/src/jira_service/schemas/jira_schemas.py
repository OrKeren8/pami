from typing import List, Optional

from pydantic import BaseModel, Field


class CreateIssueRequest(BaseModel):
    project_key: str
    summary: str
    description: Optional[str] = None
    issue_type: str = "Task"
    priority: Optional[str] = None
    due_date: Optional[str] = None
    labels: List[str] = Field(default_factory=lambda: ["pami"])


class JiraProjectResponse(BaseModel):
    id: str
    key: str
    name: str
    project_type_key: Optional[str] = None
    simplified: Optional[bool] = None