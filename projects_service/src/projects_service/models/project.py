from beanie import Document
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel
from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on-hold"


class ProjectRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"


class ProjectMember(BaseModel):
    """Someone with access to a project.

    The owner is stored as a member row too, so "can this user see this project" is one
    membership test rather than an owner check plus a membership check - the second of which
    is the one that gets forgotten.
    """

    user_id: str
    email: Optional[str] = None
    role: ProjectRole = ProjectRole.MEMBER
    added_at: datetime = Field(default_factory=datetime.utcnow)


class PendingInvite(BaseModel):
    """An email invited to a project before that person had an account.

    Held on the project and claimed at first sign-in. Without this, sharing would only work
    with people who had already signed up, which is not how anyone invites a teammate.
    """

    email: str
    invited_by: str
    invited_at: datetime = Field(default_factory=datetime.utcnow)


class Project(Document):
    name: str
    goal: str
    status: ProjectStatus  # e.g., "active", "completed", "on-hold"
    color: Optional[str] = None
    # Optional so existing documents still load. A project with no owner is invisible to
    # everyone rather than visible to everyone - see scripts/backfill_project_owners.py.
    owner_id: Optional[str] = None
    members: List[ProjectMember] = Field(default_factory=list)
    pending_invites: List[PendingInvite] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def member_ids(self) -> set[str]:
        return {member.user_id for member in self.members}

    def role_of(self, user_id: str) -> Optional[ProjectRole]:
        for member in self.members:
            if member.user_id == user_id:
                return member.role
        return None

    class Settings:
        name = "projects"
        # "List the projects I can see" runs on every dashboard load and is a scan without
        # these; the collection had no indexes at all. The invite index backs claiming
        # invites at sign-in, which happens for every user on every login.
        indexes = [
            IndexModel([("members.user_id", ASCENDING)], name="member"),
            IndexModel([("pending_invites.email", ASCENDING)], name="invite_email"),
            IndexModel([("owner_id", ASCENDING)], name="owner"),
        ]
