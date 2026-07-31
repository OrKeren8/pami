from datetime import datetime
from typing import List, Optional

from loguru import logger
from pymongo.errors import DuplicateKeyError

from projects_service.core.auth import AuthenticatedUser
from projects_service.data.project_repository import ProjectRepository
from projects_service.models.project import ProjectMember, ProjectRole
from projects_service.models.user import User


class UserDirectory:
    """Who exists, and what they were invited to before they existed."""

    def __init__(self, project_repository: ProjectRepository):
        self._logger = logger.bind(service="UserDirectory")
        self._project_repository = project_repository

    async def record_sign_in(self, user: AuthenticatedUser) -> Optional[User]:
        """Upsert the caller into the mirror and claim any invites for their email.

        Called on sign-in rather than lazily, because an invite sent to someone with no
        account yet has to become real membership at some definite moment, and first sign-in
        is the only moment we can be sure the address belongs to them.
        """
        if not user.email:
            self._logger.warning(
                f"Sign-in for {user.user_id} carried no email; cannot mirror or claim invites"
            )
            return None

        record = await User.find_one(User.sub == user.user_id)
        if record:
            record.email = user.email
            record.last_seen_at = datetime.utcnow()
            record.sign_in_count += 1
            await record.save()
        else:
            record = User(
                sub=user.user_id,
                email=user.email,
                last_seen_at=datetime.utcnow(),
                sign_in_count=1,
            )
            try:
                await record.insert()
            except DuplicateKeyError:
                # Two tabs signing in at once, or an email that already belongs to another
                # subject. Neither is worth failing the request over.
                self._logger.info(f"User record for {user.email} already existed")
                record = await User.find_one(User.sub == user.user_id)

        claimed = await self.claim_pending_invites(user)
        if claimed:
            self._logger.info(f"{user.email} claimed {claimed} pending invite(s)")
        return record

    async def claim_pending_invites(self, user: AuthenticatedUser) -> int:
        """Turn invites addressed to this email into real membership."""
        if not user.email:
            return 0

        projects = await self._project_repository.list_with_pending_invite(user.email)
        claimed = 0
        for project in projects:
            remaining = [
                invite
                for invite in project.pending_invites
                if invite.email.lower() != user.email
            ]
            if len(remaining) == len(project.pending_invites):
                continue

            members = list(project.members)
            if user.user_id not in {member.user_id for member in members}:
                members.append(
                    ProjectMember(
                        user_id=user.user_id,
                        email=user.email,
                        role=ProjectRole.MEMBER,
                    )
                )

            await self._project_repository.update(
                str(project.id),
                {
                    "members": [member.model_dump() for member in members],
                    "pending_invites": [invite.model_dump() for invite in remaining],
                },
            )
            claimed += 1
        return claimed

    async def find_by_email(self, email: str) -> Optional[User]:
        return await User.find_one(User.email == email.strip().lower())

    async def list_users(self) -> List[User]:
        """Every known user, newest first. Admin dashboard only."""
        return await User.find_all().sort("-created_at").to_list()

    async def emails_for(self, user_ids: List[str]) -> dict:
        """Map subjects to emails, for showing who a project is shared with."""
        if not user_ids:
            return {}
        records = await User.find({"sub": {"$in": list(set(user_ids))}}).to_list()
        return {record.sub: record.email for record in records}
