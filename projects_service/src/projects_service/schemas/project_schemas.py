from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on-hold"


class CreateProjectRequest(BaseModel):
    name: str
    goal: str
    status: ProjectStatus = ProjectStatus.ACTIVE
    color: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[ProjectStatus] = None
    color: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    goal: str
    status: ProjectStatus
    color: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InviteMemberRequest(BaseModel):
    # EmailStr would be better, but it pulls in email-validator; the address is lowercased
    # and matched exactly against the user mirror, so a malformed one simply finds nobody and
    # becomes a pending invite that can never be claimed.
    email: str


class ProjectMemberPayload(BaseModel):
    user_id: str
    email: Optional[str] = None
    role: str
    added_at: datetime


class PendingInvitePayload(BaseModel):
    email: str
    invited_by: str
    invited_at: datetime


class ProjectMembersResponse(BaseModel):
    owner_id: Optional[str] = None
    members: List[ProjectMemberPayload] = Field(default_factory=list)
    pending_invites: List[PendingInvitePayload] = Field(default_factory=list)
