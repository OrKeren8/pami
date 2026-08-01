from __future__ import annotations

from pydantic import BaseModel, Field


class CreateIssueRequest(BaseModel):
    project_key: str
    summary: str
    description: str | None = None
    issue_type: str = "Task"
    priority: str | None = None
    due_date: str | None = None
    labels: list[str] = Field(default_factory=lambda: ["pami"])


class JiraProjectResponse(BaseModel):
    id: str
    key: str
    name: str
    project_type_key: str | None = None
    simplified: bool | None = None
