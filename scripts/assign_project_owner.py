"""Give an ownerless project an owner.

Projects created before ownership existed have `owner_id: null` and no members. With a real
identity in play that makes them invisible: `GET /projects/` returns the caller's own projects,
and the "also show unowned ones" fallback applies only to the anonymous stand-in identity - so
an anonymous curl sees them and a signed-in user does not. No user route can fix it either,
because sharing a project requires being its owner and there is nobody to be.

This is the same write the admin endpoint `POST /admin/projects/{id}/owner` performs. It exists
because that endpoint is a backend deploy away, and because a data change to a live database
should be something a person runs deliberately and can read first.

Deliberately narrow:
  * only touches projects with no members, so it can never take one over;
  * requires an account that has signed in at least once, so the owner id is a real Cognito
    subject rather than a typo;
  * prints the plan and changes nothing unless you pass --apply.

Usage
-----
    py scripts/assign_project_owner.py --email you@example.com                 # dry run
    py scripts/assign_project_owner.py --email you@example.com --apply
    py scripts/assign_project_owner.py --email you@example.com --project pami --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover - the service's own dependency
    sys.exit("pymongo is missing. Run this from projects_service, or `uv pip install pymongo`.")

DEFAULT_ENV = Path(__file__).resolve().parent.parent / "projects_service" / ".env"

# The identity the service uses when a request carries no token, from
# projects_service.core.config. It is not a person, so a project "owned" by it has no real
# owner - which is what happens when a project is created through the API unauthenticated.
STAND_IN_USER = "local-dev-user"


def read_env(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"No env file at {path}. Pass --url and --database instead.")
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.strip().startswith("#")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="who should own the project")
    parser.add_argument(
        "--project",
        default=None,
        help="a project name or id; omit to take every ownerless project",
    )
    parser.add_argument("--url", default=None, help="Mongo connection string")
    parser.add_argument("--database", default=None, help="database name")
    parser.add_argument("--env", default=str(DEFAULT_ENV), help="env file to read")
    parser.add_argument(
        "--apply", action="store_true", help="actually write; without it, only report"
    )
    args = parser.parse_args()

    url = args.url
    database = args.database
    if not url or not database:
        env = read_env(Path(args.env))
        url = url or env.get("MONGODB_URL", "").strip()
        database = database or env.get("DATABASE_NAME", "pami").strip()
    if not url:
        return int(bool(sys.stderr.write("No Mongo URL found.\n")))

    client = MongoClient(url, serverSelectionTimeoutMS=15000)
    db = client[database]

    user = db["users"].find_one({"email": args.email.strip().lower()})
    if not user or not user.get("sub"):
        signed_in = sorted(
            row.get("email", "?") for row in db["users"].find({}, {"email": 1})
        )
        return int(
            bool(
                sys.stderr.write(
                    f"No account for {args.email} has signed in yet. "
                    f"Known accounts: {', '.join(signed_in) or 'none'}\n"
                )
            )
        )

    # A project belongs to nobody when it has no members at all, or when its only member is
    # the stand-in identity. owner_id alone is not the test: the owner is stored as a member
    # row too, and membership is what read access checks.
    ownerless = {
        "$or": [
            {"members": {"$size": 0}},
            {"members": {"$exists": False}},
            {"members": {"$size": 1}, "members.user_id": STAND_IN_USER},
        ]
    }
    candidates = [
        doc
        for doc in db["projects"].find(ownerless, {"name": 1})
        if args.project is None
        or args.project == str(doc["_id"])
        or args.project.lower() == (doc.get("name") or "").lower()
    ]

    if not candidates:
        print("Nothing to do: no ownerless project matched.")
        return 0

    nodes = db["context_tree"]
    print(f"{args.email} -> {user['sub']}")
    for doc in candidates:
        count = nodes.count_documents({"project_id": str(doc["_id"])})
        print(f"  {doc.get('name')} ({doc['_id']}) - {count} nodes")

    if not args.apply:
        print("\nDry run. Re-run with --apply to make these changes.")
        return 0

    owner = {
        "user_id": user["sub"],
        "email": user.get("email"),
        "role": "owner",
        "added_at": datetime.utcnow(),
    }
    changed = 0
    for doc in candidates:
        # The ownerless condition is repeated in the filter, not just used to select: between
        # the read above and this write, someone could have signed in and claimed an invite.
        result = db["projects"].update_one(
            {"_id": doc["_id"], **ownerless},
            {
                "$set": {
                    "owner_id": user["sub"],
                    "members": [owner],
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        changed += result.modified_count
        state = "assigned" if result.modified_count else "skipped (no longer ownerless)"
        print(f"  {doc.get('name')}: {state}")

    print(f"\n{changed} project(s) now belong to {args.email}. Reload the app to see them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
