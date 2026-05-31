from pydantic import BaseModel
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
