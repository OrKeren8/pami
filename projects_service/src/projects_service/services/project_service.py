from typing import List, Optional
from datetime import datetime
from loguru import logger

from projects_service.data.project_repository import ProjectRepository
from projects_service.models.project import (
    PendingInvite,
    Project,
    ProjectMember,
    ProjectRole,
)
from projects_service.schemas.project_schemas import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
)


class ProjectService:
    """Service for project business logic."""

    def __init__(self, project_repository: ProjectRepository):
        self._logger = logger.bind(service="ProjectService")
        self._project_repository = project_repository

    async def create_project(
        self,
        request: CreateProjectRequest,
        owner_id: str,
        owner_email: Optional[str] = None,
    ) -> ProjectResponse:
        """Create a new project owned by the caller."""
        # The owner is also a member row, so membership is the single access test.
        project = Project(
            name=request.name,
            goal=request.goal,
            status=request.status,
            color=request.color,
            owner_id=owner_id,
            members=[
                ProjectMember(
                    user_id=owner_id, email=owner_email, role=ProjectRole.OWNER
                )
            ],
        )
        created_project = await self._project_repository.create(project)

        color_val = getattr(created_project, "color", None)
        color = color_val if isinstance(color_val, str) else None

        return ProjectResponse(
            id=str(created_project.id),
            name=created_project.name,
            goal=created_project.goal,
            status=created_project.status,
            color=color,
            created_at=created_project.created_at,
            updated_at=created_project.updated_at,
        )

    async def get_project(self, project_id: str) -> Optional[ProjectResponse]:
        """Get a project by ID."""
        project = await self._project_repository.get_by_id(project_id)
        if not project:
            return None

        color_val = getattr(project, "color", None)
        color = color_val if isinstance(color_val, str) else None

        return ProjectResponse(
            id=str(project.id),
            name=project.name,
            goal=project.goal,
            status=project.status,
            color=color,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def list_projects(self, user_id: str) -> List[ProjectResponse]:
        """The projects this user owns or was added to."""
        projects = await self._project_repository.list_for_member(user_id)
        return [
            ProjectResponse(
                id=str(p.id),
                name=p.name,
                goal=p.goal,
                status=p.status,
                color=(
                    getattr(p, "color", None)
                    if isinstance(getattr(p, "color", None), str)
                    else None
                ),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in projects
        ]

    async def update_project(
        self, project_id: str, request: UpdateProjectRequest
    ) -> Optional[ProjectResponse]:
        """Update a project."""
        update_data = request.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        project = await self._project_repository.update(project_id, update_data)
        if not project:
            return None

        color_val = getattr(project, "color", None)
        return ProjectResponse(
            id=str(project.id),
            name=project.name,
            goal=project.goal,
            status=project.status,
            color=str(color_val) if color_val is not None else None,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        return await self._project_repository.delete(project_id)

    async def add_member_by_email(
        self,
        project: Project,
        email: str,
        invited_by: str,
        existing_user: Optional[object] = None,
    ) -> dict:
        """Share a project with an email address.

        If the address has an account it becomes a member immediately. If not, the invite is
        held on the project and claimed the first time that address signs in - otherwise
        sharing would only work with people who had already signed up.
        """
        email = email.strip().lower()
        if not email:
            raise ValueError("An email address is required")

        if existing_user is not None:
            if existing_user.sub in project.member_ids():
                return {"status": "already_member", "email": email}

            members = [member.model_dump() for member in project.members]
            members.append(
                ProjectMember(
                    user_id=existing_user.sub, email=email, role=ProjectRole.MEMBER
                ).model_dump()
            )
            await self._project_repository.update(
                str(project.id), {"members": members, "updated_at": datetime.utcnow()}
            )
            self._logger.info(f"Added {email} to project {project.id}")
            return {"status": "added", "email": email}

        if any(invite.email.lower() == email for invite in project.pending_invites):
            return {"status": "already_invited", "email": email}

        invites = [invite.model_dump() for invite in project.pending_invites]
        invites.append(PendingInvite(email=email, invited_by=invited_by).model_dump())
        await self._project_repository.update(
            str(project.id),
            {"pending_invites": invites, "updated_at": datetime.utcnow()},
        )
        self._logger.info(f"Invited {email} to project {project.id}; no account yet")
        return {"status": "invited", "email": email}

    async def remove_member(self, project: Project, user_id: str) -> bool:
        """Revoke access. The owner cannot be removed - that would orphan the project.

        Their conversations stay with the project. Deleting them would destroy the shared
        memory the project exists to hold, which is not what "remove this person" means.
        """
        if user_id == project.owner_id:
            raise ValueError("The owner cannot be removed from their own project")

        members = [
            member.model_dump()
            for member in project.members
            if member.user_id != user_id
        ]
        if len(members) == len(project.members):
            return False

        await self._project_repository.update(
            str(project.id), {"members": members, "updated_at": datetime.utcnow()}
        )
        self._logger.info(f"Removed {user_id} from project {project.id}")
        return True

    async def cancel_invite(self, project: Project, email: str) -> bool:
        email = email.strip().lower()
        invites = [
            invite.model_dump()
            for invite in project.pending_invites
            if invite.email.lower() != email
        ]
        if len(invites) == len(project.pending_invites):
            return False
        await self._project_repository.update(
            str(project.id),
            {"pending_invites": invites, "updated_at": datetime.utcnow()},
        )
        return True
