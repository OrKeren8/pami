"""Delete a project and everything under it: nodes, tasks, and stored transcripts.

Exists because the app has no way to do it. Deleting a project through the API leaves its
context nodes and its S3 transcripts behind, and a node whose transcript is gone is exactly the
dead weight this is meant to clear - so a partial delete would create more of the problem.

Deliberately narrow, because it is irreversible:
  * one project at a time, named explicitly;
  * refuses a project owned by anyone but the address given, so it cannot delete a
    collaborator's work by mistake;
  * reports everything it would remove and changes nothing without --apply.

Usage
-----
    py scripts/purge_project.py --project pami --owner you@example.com
    py scripts/purge_project.py --project pami --owner you@example.com --apply
    py scripts/purge_project.py --project pami --owner you@example.com --apply --keep-project
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from bson import ObjectId
    from pymongo import MongoClient
except ImportError:  # pragma: no cover
    sys.exit("pymongo is missing. Run from projects_service, or `uv pip install pymongo`.")

DEFAULT_ENV = Path(__file__).resolve().parent.parent / "projects_service" / ".env"


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
    parser.add_argument("--project", required=True, help="project name or id")
    parser.add_argument("--owner", required=True, help="the email that must own it")
    parser.add_argument("--bucket", default=None, help="transcript bucket, for S3 deletion")
    parser.add_argument("--url", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    parser.add_argument(
        "--keep-project",
        action="store_true",
        help="empty it but keep the project itself",
    )
    parser.add_argument("--apply", action="store_true", help="actually delete")
    args = parser.parse_args()

    url, database = args.url, args.database
    if not url or not database:
        env = read_env(Path(args.env))
        url = url or env.get("MONGODB_URL", "").strip()
        database = database or env.get("DATABASE_NAME", "pami").strip()

    db = MongoClient(url, serverSelectionTimeoutMS=15000)[database]

    owner = db["users"].find_one({"email": args.owner.strip().lower()})
    if not owner:
        return int(bool(sys.stderr.write(f"No account for {args.owner}.\n")))

    query = {"name": args.project}
    if ObjectId.is_valid(args.project):
        query = {"_id": ObjectId(args.project)}
    matches = list(db["projects"].find(query, {"name": 1, "owner_id": 1}))
    if not matches:
        return int(bool(sys.stderr.write(f"No project matched {args.project!r}.\n")))
    if len(matches) > 1:
        ids = ", ".join(str(m["_id"]) for m in matches)
        return int(
            bool(sys.stderr.write(f"{args.project!r} is ambiguous. Pass an id: {ids}\n"))
        )

    project = matches[0]
    if project.get("owner_id") != owner["sub"]:
        return int(
            bool(
                sys.stderr.write(
                    f"{project.get('name')!r} is not owned by {args.owner}. Refusing.\n"
                )
            )
        )

    pid = str(project["_id"])
    nodes = list(db["context_tree"].find({"project_id": pid}, {"conversation_id": 1}))
    tasks = db["tasks"].count_documents({"project_id": pid})
    conversations = sorted({n["conversation_id"] for n in nodes if n.get("conversation_id")})

    print(f"{project.get('name')!r} ({pid}) owned by {args.owner}")
    print(f"  context nodes : {len(nodes)}")
    print(f"  tasks         : {tasks}")
    print(f"  transcripts   : {len(conversations)}")
    print(f"  the project   : {'kept' if args.keep_project else 'deleted'}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to delete this.")
        return 0

    removed_nodes = db["context_tree"].delete_many({"project_id": pid}).deleted_count
    removed_tasks = db["tasks"].delete_many({"project_id": pid}).deleted_count
    print(f"\ndeleted {removed_nodes} nodes, {removed_tasks} tasks")

    if args.bucket and conversations:
        try:
            import boto3

            s3 = boto3.client("s3")
            # Batched: one call per thousand keys is the API's own limit, and a loop of
            # single deletes on a large project is slow enough to look hung.
            for start in range(0, len(conversations), 1000):
                batch = conversations[start : start + 1000]
                s3.delete_objects(
                    Bucket=args.bucket,
                    Delete={"Objects": [{"Key": f"{c}.json"} for c in batch]},
                )
            print(f"deleted {len(conversations)} transcripts from {args.bucket}")
        except Exception as error:  # pragma: no cover - reported, not raised
            print(f"could not delete transcripts ({error}); the ids are listed above")

    if not args.keep_project:
        db["projects"].delete_one({"_id": project["_id"]})
        print("deleted the project")

    return 0


if __name__ == "__main__":
    sys.exit(main())
