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
    # Jira Cloud identifies people by accountId, not by name or email: a display name is
    # ambiguous, and email is hidden by default under Atlassian's privacy settings.
    assignee_account_id: str | None = None


class JiraProjectResponse(BaseModel):
    id: str
    key: str
    name: str
    project_type_key: str | None = None
    simplified: bool | None = None


class JiraUserResponse(BaseModel):
    account_id: str
    display_name: str
    email: str | None = None
    active: bool = True


class AddCommentRequest(BaseModel):
    body: str
