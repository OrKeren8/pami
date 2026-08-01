"""Ownership, sharing and the admin gate, through the real routes.

The interesting cases here are all negative: what a caller must *not* be able to reach. Before
this, `GET /projects/` returned every project in the database and passing any project id was
enough to read the resources under it.
"""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from projects_service.api.v1.admin import router as admin_router
from projects_service.api.v1.projects import router as projects_router
from projects_service.api.v1.session import router as session_router
from projects_service.core.auth import AuthenticatedUser, current_user
from projects_service.dependencies import (
    get_context_tree_service,
    get_project_repository,
    get_project_service,
    get_task_service,
    get_user_directory,
)
from projects_service.models.project import (
    PendingInvite,
    Project,
    ProjectMember,
    ProjectRole,
)
from projects_service.services import project_service as project_service_module
from projects_service.services.project_service import ProjectService

OWNER = AuthenticatedUser("owner-sub", "owner@example.com", [])
OUTSIDER = AuthenticatedUser("outsider-sub", "outsider@example.com", [])
INVITEE = AuthenticatedUser("invitee-sub", "invitee@example.com", [])
ADMIN = AuthenticatedUser("admin-sub", "orkerem8@gmail.com", [])


class FakeProjectDoc:
    """A Project-shaped document the in-memory repository can hand back."""

    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", str(uuid4()))
        self.name = kwargs.pop("name", "Project")
        self.goal = kwargs.pop("goal", "Goal")
        self.status = kwargs.pop("status", "active")
        self.color = kwargs.pop("color", None)
        self.owner_id = kwargs.pop("owner_id", None)
        self.members = kwargs.pop("members", [])
        self.pending_invites = kwargs.pop("pending_invites", [])
        self.created_at = kwargs.pop("created_at", datetime.utcnow())
        self.updated_at = kwargs.pop("updated_at", datetime.utcnow())

    def member_ids(self):
        return {member.user_id for member in self.members}

    def role_of(self, user_id):
        for member in self.members:
            if member.user_id == user_id:
                return member.role
        return None


class InMemoryProjectRepository:
    def __init__(self):
        self.projects: dict[str, FakeProjectDoc] = {}

    async def create(self, project: Project, session=None):
        doc = FakeProjectDoc(
            name=project.name,
            goal=project.goal,
            status=project.status,
            owner_id=project.owner_id,
            members=list(project.members),
        )
        self.projects[str(doc.id)] = doc
        return doc

    async def get_by_id(self, project_id: str, session=None):
        return self.projects.get(str(project_id))

    async def list_for_member(self, user_id: str, session=None, include_unowned=False):
        return [
            project
            for project in self.projects.values()
            if user_id in project.member_ids()
            or (include_unowned and not project.members)
        ]

    async def list_all_for_admin(self, session=None):
        return list(self.projects.values())

    async def list_with_pending_invite(self, email: str, session=None):
        return [
            project
            for project in self.projects.values()
            if any(
                invite.email.lower() == email.lower()
                for invite in project.pending_invites
            )
        ]

    async def update(self, project_id: str, update_data: dict, session=None):
        project = self.projects.get(str(project_id))
        if not project:
            return None
        for key, value in update_data.items():
            if key == "members":
                value = [ProjectMember(**item) for item in value]
            if key == "pending_invites":
                value = [PendingInvite(**item) for item in value]
            setattr(project, key, value)
        return project

    async def delete(self, project_id: str, session=None):
        return self.projects.pop(str(project_id), None) is not None


class FakeUserDirectory:
    def __init__(self, repository):
        self.repository = repository
        self.users = {}

    def add(self, user: AuthenticatedUser):
        record = type(
            "UserRecord",
            (),
            {
                "sub": user.user_id,
                "email": user.email,
                "created_at": datetime.utcnow(),
                "last_seen_at": datetime.utcnow(),
                "sign_in_count": 1,
            },
        )()
        self.users[user.email] = record
        return record

    async def find_by_email(self, email: str):
        return self.users.get(email.strip().lower())

    async def list_users(self):
        return list(self.users.values())

    async def record_sign_in(self, user):
        return self.add(user)

    async def claim_pending_invites(self, user: AuthenticatedUser):
        projects = await self.repository.list_with_pending_invite(user.email)
        claimed = 0
        for project in projects:
            project.pending_invites = [
                invite
                for invite in project.pending_invites
                if invite.email.lower() != user.email
            ]
            if user.user_id not in project.member_ids():
                project.members = list(project.members) + [
                    ProjectMember(
                        user_id=user.user_id, email=user.email, role=ProjectRole.MEMBER
                    )
                ]
            claimed += 1
        return claimed


@pytest.fixture
def app_context(monkeypatch):
    # The service builds a real Beanie document, which needs an initialised collection. The
    # behaviour under test is authorization, not persistence, so the document is faked - the
    # same approach test_context_tree_e2e.py takes for ContextTreeNode.
    monkeypatch.setattr(project_service_module, "Project", FakeProjectDoc, raising=True)

    repository = InMemoryProjectRepository()
    directory = FakeUserDirectory(repository)
    service = ProjectService(repository)

    app = FastAPI()
    app.include_router(projects_router)
    app.include_router(session_router)
    app.include_router(admin_router)

    app.dependency_overrides[get_project_repository] = lambda: repository
    app.dependency_overrides[get_project_service] = lambda: service
    app.dependency_overrides[get_user_directory] = lambda: directory
    app.dependency_overrides[get_context_tree_service] = lambda: None
    app.dependency_overrides[get_task_service] = lambda: None

    def as_user(user: AuthenticatedUser):
        app.dependency_overrides[current_user] = lambda: user

    as_user(OWNER)
    return app, TestClient(app), repository, directory, as_user


def _create_project(client, name="Mine"):
    response = client.post(
        "/projects/", json={"name": name, "goal": "Goal", "status": "active"}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_projects_are_listed_per_user(app_context):
    _, client, _, _, as_user = app_context
    _create_project(client, "Owner project")

    assert [p["name"] for p in client.get("/projects/").json()] == ["Owner project"]

    as_user(OUTSIDER)
    assert client.get("/projects/").json() == [], (
        "a different user must not see someone else's projects"
    )


def test_outsider_cannot_read_a_project_by_id(app_context):
    _, client, _, _, as_user = app_context
    project_id = _create_project(client)

    as_user(OUTSIDER)
    response = client.get(f"/projects/{project_id}")

    # 404, not 403: 403 would confirm the project exists.
    assert response.status_code == 404


def test_outsider_cannot_delete_or_rename_a_project(app_context):
    _, client, _, _, as_user = app_context
    project_id = _create_project(client)

    as_user(OUTSIDER)
    assert (
        client.put(f"/projects/{project_id}", json={"name": "Hijacked"}).status_code
        == 404
    )
    assert client.delete(f"/projects/{project_id}").status_code == 404


def test_sharing_by_email_adds_an_existing_user(app_context):
    _, client, repository, directory, as_user = app_context
    project_id = _create_project(client, "Shared")
    directory.add(INVITEE)

    response = client.post(
        f"/projects/{project_id}/members", json={"email": "invitee@example.com"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "added"

    as_user(INVITEE)
    assert [p["name"] for p in client.get("/projects/").json()] == ["Shared"]


def test_invite_to_an_address_with_no_account_is_claimed_at_sign_in(app_context):
    _, client, repository, directory, as_user = app_context
    project_id = _create_project(client, "Shared later")

    response = client.post(
        f"/projects/{project_id}/members", json={"email": "invitee@example.com"}
    )
    assert response.json()["status"] == "invited", (
        "an address with no account yet must not be silently dropped"
    )

    # They sign up and sign in for the first time.
    as_user(INVITEE)
    assert client.post("/session/").status_code == 200
    assert [p["name"] for p in client.get("/projects/").json()] == ["Shared later"]


def test_a_member_cannot_invite_others_or_delete_the_project(app_context):
    _, client, _, directory, as_user = app_context
    project_id = _create_project(client, "Shared")
    directory.add(INVITEE)
    client.post(
        f"/projects/{project_id}/members", json={"email": "invitee@example.com"}
    )

    as_user(INVITEE)
    assert client.get(f"/projects/{project_id}").status_code == 200, "member can read"
    assert (
        client.post(
            f"/projects/{project_id}/members", json={"email": "someone@else.com"}
        ).status_code
        == 403
    ), "a member handing the project to anyone else would defeat the owner's control"
    assert client.delete(f"/projects/{project_id}").status_code == 403


def test_removing_a_member_revokes_access(app_context):
    _, client, _, directory, as_user = app_context
    project_id = _create_project(client, "Shared")
    directory.add(INVITEE)
    client.post(
        f"/projects/{project_id}/members", json={"email": "invitee@example.com"}
    )

    assert (
        client.delete(f"/projects/{project_id}/members/{INVITEE.user_id}").status_code
        == 200
    )

    as_user(INVITEE)
    assert client.get(f"/projects/{project_id}").status_code == 404


def test_the_owner_cannot_be_removed(app_context):
    _, client, _, _, _ = app_context
    project_id = _create_project(client)

    response = client.delete(f"/projects/{project_id}/members/{OWNER.user_id}")

    assert response.status_code == 422, "removing the owner would orphan the project"


def test_admin_dashboard_is_refused_to_everyone_else(app_context):
    _, client, _, directory, as_user = app_context
    directory.add(OWNER)
    _create_project(client)

    assert client.get("/admin/users").status_code == 403

    as_user(ADMIN)
    response = client.get("/admin/users")
    assert response.status_code == 200
    body = response.json()
    assert body["total_projects"] == 1
    assert any(row["email"] == "owner@example.com" for row in body["users"])


def test_unowned_projects_stay_reachable_while_auth_is_off(app_context, monkeypatch):
    """The bridge that keeps a deploy from emptying the app.

    Ownership arrives before anyone has signed in, so the projects that predate it have nobody
    to belong to. While AUTH_REQUIRED is off every request is the same stand-in user, and that
    user can still see them - otherwise deploying this would hide the existing projects until
    the backfill ran.
    """
    from projects_service.core.config import settings

    monkeypatch.setattr(settings, "auth_required", False, raising=False)
    _, client, repository, _, as_user = app_context
    orphan = FakeProjectDoc(name="Legacy", owner_id=None, members=[])
    repository.projects[str(orphan.id)] = orphan

    as_user(AuthenticatedUser(settings.unauthenticated_user_id, "local@pami.dev", []))

    assert [p["name"] for p in client.get("/projects/").json()] == ["Legacy"]
    assert client.get(f"/projects/{orphan.id}").status_code == 200

    # A real signed-in user is not the stand-in, so the allowance does not reach them.
    as_user(OUTSIDER)
    assert client.get("/projects/").json() == []
    assert client.get(f"/projects/{orphan.id}").status_code == 404


def test_unowned_projects_are_hidden_once_auth_is_required(app_context, monkeypatch):
    """With authentication on, the bridge must be gone."""
    from projects_service.core.config import settings

    monkeypatch.setattr(settings, "auth_required", True, raising=False)
    _, client, repository, _, as_user = app_context
    orphan = FakeProjectDoc(name="Legacy", owner_id=None, members=[])
    repository.projects[str(orphan.id)] = orphan

    as_user(AuthenticatedUser(settings.unauthenticated_user_id, "local@pami.dev", []))

    assert client.get("/projects/").json() == []
    assert client.get(f"/projects/{orphan.id}").status_code == 404


def test_a_project_with_no_owner_is_visible_to_nobody(app_context, monkeypatch):
    from projects_service.core.config import settings

    monkeypatch.setattr(settings, "auth_required", True, raising=False)
    _, client, repository, _, as_user = app_context
    # Pre-migration shape: no owner, no members.
    orphan = FakeProjectDoc(name="Legacy", owner_id=None, members=[])
    repository.projects[str(orphan.id)] = orphan

    assert client.get("/projects/").json() == []
    assert client.get(f"/projects/{orphan.id}").status_code == 404

    as_user(ADMIN)
    assert client.get("/admin/users").json()["orphaned_projects"] == 1, (
        "an unreachable project must be surfaced, not silently ignored"
    )
