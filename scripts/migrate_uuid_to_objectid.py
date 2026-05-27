"""
Migration script: convert context_tree documents whose _id is a UUID string
into new documents with Mongo ObjectId (_id). Update references inside the
`context_tree` collection (parent_id and children_ids) to point at the new
stringified ObjectId values.

Usage:
    python scripts/migrate_uuid_to_objectid.py --dry-run
    python scripts/migrate_uuid_to_objectid.py --apply

Options:
    --mongo-uri   MongoDB connection URI (default from env MONGODB_URI or projects_service settings)
    --db-name     Database name (default 'pami')
    --collection  Collection name (default 'context_tree')
    --dry-run     Print actions that would be performed, don't modify DB
    --apply       Actually perform changes (must be explicit)

Notes:
- This script updates only the `context_tree` collection (document _id change)
  and replaces references to the old UUID string in `parent_id` and `children_ids`
  inside `context_tree` documents.
- It does NOT update external systems (S3, AI conversations). You must manually
  update any external references to the old node ids (search codebase/logs).
- Always backup your DB before running with `--apply`.
"""

import argparse
import re
import sys
from pprint import pprint
from bson import ObjectId
from pymongo import MongoClient

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def connect(uri, db_name):
    client = MongoClient(uri)
    db = client[db_name]
    return db


def find_uuid_docs(coll):
    # find docs whose _id is a string and looks like a UUID
    docs = []
    cursor = coll.find({"_id": {"$type": "string"}})
    for d in cursor:
        if isinstance(d.get("_id"), str) and UUID_RE.match(d["_id"]):
            docs.append(d)
    return docs


def migrate(db, collection_name="context_tree", dry_run=True):
    coll = db[collection_name]
    uuid_docs = find_uuid_docs(coll)
    mapping = {}
    if not uuid_docs:
        print("No UUID _id documents found in collection.")
        return mapping

    print(f"Found {len(uuid_docs)} UUID _id documents in '{collection_name}'.")

    for doc in uuid_docs:
        old_id = doc["_id"]
        new_oid = ObjectId()
        new_id_str = str(new_oid)
        mapping[old_id] = new_id_str

        print("\n---")
        print(f"Old _id: {old_id} -> New ObjectId: {new_oid} ({new_id_str})")

        if dry_run:
            # show a preview of the document with new _id
            preview = dict(doc)
            preview["_id"] = new_oid
            if "id" in preview and preview["id"] == old_id:
                preview["id"] = new_id_str
            print("Preview new document (dry-run):")
            pprint(preview)

            # show documents that would be updated referencing this id
            parents = list(coll.find({"parent_id": old_id}, {"_id": 1, "parent_id": 1}))
            children = list(
                coll.find({"children_ids": old_id}, {"_id": 1, "children_ids": 1})
            )
            print(
                f"Would update {len(parents)} parent(s) and {len(children)} children-containing document(s)."
            )
            continue

        # Apply changes
        # 1) Insert new document with ObjectId _id
        new_doc = dict(doc)
        new_doc["_id"] = new_oid
        # Normalize 'id' field if present
        if "id" in new_doc and new_doc["id"] == old_id:
            new_doc["id"] = new_id_str
        # If there are any fields that contain the old id (unlikely here), keep them for now
        # Insert new document
        try:
            coll.insert_one(new_doc)
            print(f"Inserted new document with _id {new_oid}.")
        except Exception as e:
            print(f"Failed to insert new document for {old_id}: {e}")
            continue

        # 2) Update parent_id references
        res_parent = coll.update_many(
            {"parent_id": old_id}, {"$set": {"parent_id": new_id_str}}
        )
        print(f"Updated {res_parent.modified_count} parent_id references.")

        # 3) Update children_ids arrays: replace occurrences of old_id with new_id_str
        children_cursor = coll.find({"children_ids": old_id})
        updated_count = 0
        for cdoc in children_cursor:
            c_children = cdoc.get("children_ids", [])
            new_children = [new_id_str if x == old_id else x for x in c_children]
            if new_children != c_children:
                coll.update_one(
                    {"_id": cdoc["_id"]}, {"$set": {"children_ids": new_children}}
                )
                updated_count += 1
        print(f"Updated children_ids in {updated_count} documents.")

        # 4) (Optional) Update other collections within same DB where exact string matches occur.
        # For safety, do not mass-replace across DB automatically. Print instructions instead.
        print(
            "Note: This script updates only the 'context_tree' collection. If other collections"
        )
        print(
            "refer to context node ids (e.g. ai conversations stored externally), you must update them manually."
        )

        # 5) Delete old document
        del_res = coll.delete_one({"_id": old_id})
        print(
            f"Deleted old document with _id {old_id}: deleted_count={del_res.deleted_count}"
        )

    return mapping


def main():
    parser = argparse.ArgumentParser(
        description="Migrate UUID _id in context_tree to ObjectId"
    )
    parser.add_argument("--mongo-uri", default=None)
    parser.add_argument("--db-name", default=None)
    parser.add_argument("--collection", default="context_tree")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")

    args = parser.parse_args()

    # Resolve defaults from projects_service settings if available
    default_uri = "mongodb://localhost:27017"
    default_db = "pami"
    try:
        from projects_service.src.projects_service.core.config import (
            settings as ps_settings,
        )

        default_uri = getattr(ps_settings, "mongodb_url", default_uri)
        default_db = getattr(ps_settings, "database_name", default_db)
    except Exception:
        # fallback if running standalone
        pass

    mongo_uri = args.mongo_uri or default_uri
    db_name = args.db_name or default_db

    if args.apply and args.dry_run:
        print("Cannot use both --dry-run and --apply. Choose one.")
        sys.exit(2)

    if not args.apply and not args.dry_run:
        print("Specify either --dry-run (preview) or --apply (perform changes).")
        sys.exit(2)

    print(
        f"Connecting to {mongo_uri}, database '{db_name}', collection '{args.collection}'"
    )
    db = connect(mongo_uri, db_name)
    mapping = migrate(db, collection_name=args.collection, dry_run=args.dry_run)

    print("\nMigration mapping (old_uuid -> new_objectid_string):")
    pprint(mapping)

    print("\nDone.")


if __name__ == "__main__":
    main()
