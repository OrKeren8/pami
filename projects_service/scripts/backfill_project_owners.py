"""Give existing projects an owner.

Everything else - context nodes, tasks, conversations, chunks - inherits access from its
project, so the entire migration is this one field plus a member row.

Why it is needed: a project with no members is visible to nobody. That is deliberate (failing
closed beats defaulting to "everyone can see it"), but it means the projects that existed
before ownership was introduced disappear from every user's list until this runs.

Usage:
    py -m uv run python scripts/backfill_project_owners.py --list
    py -m uv run python scripts/backfill_project_owners.py --owner-email you@example.com
    py -m uv run python scripts/backfill_project_owners.py --owner-email you@example.com --apply

    # Before that account has ever signed in, so there is no mirror record to look it up in.
    # The subject comes from Cognito, which is the authority on it - not a guess.
    py -m uv run python scripts/backfill_project_owners.py         --owner-email you@example.com --owner-sub <cognito-sub> --project pami --apply

Nothing is written without --apply.
"""

import argparse
import asyncio
from datetime import datetime

from beanie import init_beanie
from pymongo import AsyncMongoClient

from projects_service.core.config import settings
from projects_service.models.context_tree import ContextTreeNode
from projects_service.models.project import Project, ProjectRole
from projects_service.models.task import Task
from projects_service.models.user import User


async def _connect():
    url = settings.mongodb_url
    if "/?" in url:
        url = url.replace("/?", f"/{settings.database_name}?")
    client = AsyncMongoClient(url)
    await init_beanie(
        database=client[settings.database_name],
        document_models=[Project, Task, ContextTreeNode, User],
    )
    return client


async def main(
    owner_email: str | None,
    apply: bool,
    list_only: bool,
    owner_sub: str | None = None,
    only_project: str | None = None,
) -> None:
    client = await _connect()
    try:
        projects = await Project.find_all().to_list()
        unowned = [project for project in projects if not project.members]

        if only_project:
            # Claiming one project at a time, by name or by id, so a run cannot quietly take
            # ownership of something that was left unowned on purpose.
            wanted = only_project.strip().lower()
            unowned = [
                project
                for project in unowned
                if project.name.strip().lower() == wanted
                or str(project.id) == only_project
            ]

        print(f"projects: {len(projects)}")
        print(f"without an owner{' (matching --project)' if only_project else ''}: {len(unowned)}")
        for project in unowned:
            print(f"  - {project.name} ({project.id})")

        if list_only:
            return

        if not unowned:
            print("nothing to do")
            return

        if not owner_email:
            print("\nPass --owner-email to say who these belong to.")
            return

        owner_email = owner_email.strip().lower()
        owner = await User.find_one(User.email == owner_email)

        if not owner and owner_sub:
            # The mirror is written on sign-in, so it is empty before the first one. A subject
            # read from Cognito is just as authoritative, and this is the ordinary case for the
            # very first project: it has to be claimable before anyone has logged in.
            print(f"no mirror record yet; using the subject given for {owner_email}")
            owner = User(sub=owner_sub, email=owner_email)
            if apply:
                await owner.insert()

        if not owner:
            # The mirror is written on sign-in, so a missing record means the intended owner
            # has never signed in - and guessing their Cognito subject would attach the
            # projects to an id that never authenticates.
            print(
                f"\nNo user record for {owner_email}. Sign in as that account once, then "
                f"re-run this - the subject id is only known after a sign-in."
            )
            return

        print(f"\nowner: {owner.email} ({owner.sub})")
        if not apply:
            print("dry run - pass --apply to write")
            return

        member = {
            "user_id": owner.sub,
            "email": owner.email,
            "role": ProjectRole.OWNER.value,
            "added_at": datetime.utcnow(),
        }
        for project in unowned:
            await Project.find_one(Project.id == project.id).update(
                {"$set": {"owner_id": owner.sub, "members": [member]}}
            )
            print(f"  assigned {project.name}")

        print(f"\ndone: {len(unowned)} project(s) now owned by {owner.email}")
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-email", default=None)
    parser.add_argument(
        "--owner-sub",
        default=None,
        help="Cognito subject, for an account that has not signed in yet",
    )
    parser.add_argument(
        "--project", default=None, help="claim only this project, by name or id"
    )
    parser.add_argument(
        "--apply", action="store_true", help="write the changes (default is a dry run)"
    )
    parser.add_argument(
        "--list", action="store_true", dest="list_only", help="only report what is unowned"
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            args.owner_email,
            args.apply,
            args.list_only,
            args.owner_sub,
            args.project,
        )
    )
