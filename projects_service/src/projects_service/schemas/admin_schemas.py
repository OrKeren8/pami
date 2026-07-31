from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AdminUserRow(BaseModel):
    user_id: str
    email: str
    created_at: datetime
    # Cognito exposes no last-sign-in time - UserLastModifiedDate is not one - so this comes
    # from the local mirror, which is written on every sign-in.
    last_seen_at: datetime
    sign_in_count: int
    projects_owned: int
    projects_shared: int


class AdminOverviewResponse(BaseModel):
    users: List[AdminUserRow] = Field(default_factory=list)
    total_users: int
    total_projects: int
    # Projects with no members at all: nobody can see them. Shown so a half-finished
    # migration is visible instead of looking like missing data.
    orphaned_projects: int


class SessionResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    is_admin: bool
    claimed_invites: int = 0
