"""Admin dashboard endpoints.

Gated on `current_admin`, which reads the identity from a signature-verified token. Hiding the
nav entry in the frontend is cosmetic - anyone can call an HTTP endpoint - so this is where
the restriction actually lives.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from projects_service.core.auth import CurrentAdminDep
from projects_service.data.project_repository import ProjectRepository
from projects_service.dependencies import get_project_repository, get_user_directory
from projects_service.models.project import ProjectMember, ProjectRole
from projects_service.schemas.admin_schemas import (
    AdminOverviewResponse,
    AdminUserRow,
    AdoptProjectRequest,
    UnownedProjectRow,
)
from projects_service.services.user_directory import UserDirectory

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=AdminOverviewResponse)
async def list_users(
    admin: CurrentAdminDep,
    directory: UserDirectory = Depends(get_user_directory),
    projects: ProjectRepository = Depends(get_project_repository),
):
    """Every user, with what they own and what they can see.

    Counts are computed from the projects collection rather than asked of Cognito, which
    cannot join against Mongo. Cognito is not consulted at all: it would need ListUsers, an
    IAM permission a restricted lab account may not grant, and the mirror is written on every
    sign-in.
    """
    logger.bind(component="admin").info(
        f"Admin dashboard read by {admin.email or admin.user_id}"
    )

    users = await directory.list_users()
    all_projects = await projects.list_all_for_admin()

    owned: dict[str, int] = {}
    shared: dict[str, int] = {}
    unowned: List[UnownedProjectRow] = []
    for project in all_projects:
        if not project.members:
            # No owner, so invisible to every user - the un-migrated case. Listed rather
            # than counted, because a count is not something an admin can act on.
            unowned.append(
                UnownedProjectRow(
                    id=str(project.id),
                    name=project.name,
                    created_at=project.created_at,
                )
            )
            continue
        for member in project.members:
            if member.user_id == project.owner_id:
                owned[member.user_id] = owned.get(member.user_id, 0) + 1
            else:
                shared[member.user_id] = shared.get(member.user_id, 0) + 1

    rows: List[AdminUserRow] = [
        AdminUserRow(
            user_id=user.sub,
            email=user.email,
            created_at=user.created_at,
            last_seen_at=user.last_seen_at,
            sign_in_count=user.sign_in_count,
            projects_owned=owned.get(user.sub, 0),
            projects_shared=shared.get(user.sub, 0),
        )
        for user in users
    ]

    return AdminOverviewResponse(
        users=rows,
        total_users=len(rows),
        total_projects=len(all_projects),
        orphaned_projects=len(unowned),
        unowned=unowned,
    )


@router.post("/projects/{project_id}/owner")
async def adopt_project(
    project_id: str,
    request: AdoptProjectRequest,
    admin: CurrentAdminDep,
    directory: UserDirectory = Depends(get_user_directory),
    projects: ProjectRepository = Depends(get_project_repository),
):
    """Give an ownerless project to a user, by email.

    Projects created before ownership existed have no members, so with authentication on they
    are visible to nobody and no user route can rescue them: sharing requires an owner, and
    there is none. This is the only way back, and it is deliberately narrow - it refuses a
    project that already has members, so it can never be used to take one over.
    """
    project = await projects.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="No such project")

    if project.members:
        raise HTTPException(
            status_code=409,
            detail="That project already has members. Share it from the project instead.",
        )

    user = await directory.find_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=422,
            detail=f"No account for {request.email} yet - they have to sign in once first.",
        )

    owner = ProjectMember(user_id=user.sub, email=user.email, role=ProjectRole.OWNER)
    await projects.update(
        project_id,
        {
            "owner_id": user.sub,
            "members": [owner.model_dump()],
            "updated_at": datetime.utcnow(),
        },
    )
    logger.bind(component="admin").info(
        f"{admin.email or admin.user_id} gave project {project_id} to {user.email}"
    )
    return {"message": f"{project.name} now belongs to {user.email}"}
