from typing import Literal, Optional

from pydantic import BaseModel, Field


class TicketDraft(BaseModel):
    """A Jira ticket as it stands, before anyone publishes it.

    The same object goes in and comes back out, so the model revises a draft rather than
    producing a new one each turn - which is what lets the user say "make the AC tighter"
    and keep everything else.

    Deliberately excludes the assignee and the project: those are the user's choices in the
    editor, and a model picking who does the work is not a judgement it should be making.
    """

    template_id: str = "story"
    summary: str = ""
    description: str = ""
    issue_type: str = "Story"
    priority: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = Field(default_factory=lambda: ["pami"])


class DraftMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class JiraDraftRequest(BaseModel):
    project_id: Optional[str] = None
    message: str
    draft: TicketDraft = Field(default_factory=TicketDraft)
    # The exchange so far, so "now add the edge cases" means something. Bounded by the caller.
    history: list[DraftMessage] = Field(default_factory=list)
    # What this Jira project actually offers, so the model cannot choose a type that does not
    # exist and fail at publish time.
    available_issue_types: list[str] = Field(default_factory=list)


class JiraDraftResponse(BaseModel):
    reply: str
    draft: TicketDraft
