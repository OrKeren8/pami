"""Backfill chunk + index-state records for conversations already stored in S3.

Existing conversations are invisible to cross-conversation retrieval until they are
chunked and embedded. This script is idempotent and resumable: a conversation whose
index state already covers its message count is skipped.

Usage:
    py -m uv run python scripts/backfill_conversation_index.py --dry-run
    py -m uv run python scripts/backfill_conversation_index.py --apply
    py -m uv run python scripts/backfill_conversation_index.py --apply --rescore
"""

import argparse
import asyncio

from beanie import init_beanie
from loguru import logger
from pymongo import AsyncMongoClient

from ai_conversation_service.core.config import settings
from ai_conversation_service.data.vector_index import ensure_vector_index
from ai_conversation_service.models.conversation_chunk import ConversationChunk
from ai_conversation_service.models.conversation_index_state import (
    ConversationIndexState,
)
from ai_conversation_service.services.ai_conversation_service.service import (
    AIConversationService,
)
from ai_conversation_service.services.chunk_index_service import ChunkIndexService
from ai_conversation_service.services.embedder import LocalOnnxEmbedder
from ai_conversation_service.services.projects_service_client import (
    ProjectsServiceClient,
)
from ai_conversation_service.services.reindex_trigger import ReindexTrigger


async def main(apply: bool, rescore: bool) -> None:
    conversation_service = AIConversationService()
    if not conversation_service.s3_client:
        logger.error("S3 client unavailable; cannot read transcripts")
        return

    embedder = LocalOnnxEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    client = AsyncMongoClient(settings.mongodb_url)
    database = client[settings.database_name]
    await init_beanie(
        database=database,
        document_models=[ConversationChunk, ConversationIndexState],
    )
    await ensure_vector_index(database, embedder.dimensions)

    chunk_index_service = ChunkIndexService(embedder, database)
    reindex_trigger = ReindexTrigger(
        chunk_index_service, ProjectsServiceClient(settings.projects_api_url)
    )

    keys = _list_conversation_keys(conversation_service)
    logger.info(f"Found {len(keys)} conversations in S3")

    indexed = skipped = failed = 0
    for key in keys:
        conversation_id = key.split("/")[-1].removesuffix(".json")
        conversation = await conversation_service.get_conversation(conversation_id)
        if not conversation or not conversation.messages:
            skipped += 1
            continue

        state = await chunk_index_service.state_for(conversation_id)
        if state and state.message_count_at_index >= len(conversation.messages):
            skipped += 1
            continue

        if not apply:
            logger.info(
                f"[dry-run] would index {conversation_id} "
                f"({len(conversation.messages)} messages)"
            )
            indexed += 1
            continue

        try:
            await reindex_trigger.maybe_reindex(
                conversation_id=conversation_id,
                project_id=conversation.project_id,
                node_id=state.node_id if state else conversation.context_node_id,
                messages=conversation.messages,
                header=conversation.title,
                force=True,
            )
            indexed += 1
        except Exception as error:
            logger.error(f"Failed to index {conversation_id}: {type(error).__name__}")
            failed += 1

    logger.info(f"indexed={indexed} skipped={skipped} failed={failed}")

    if rescore and apply:
        logger.info("Rescore runs as part of each reindex above")

    await client.close()


def _list_conversation_keys(conversation_service: AIConversationService) -> list[str]:
    paginator = conversation_service.s3_client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(
        Bucket=conversation_service.bucket_name, Prefix="conversations/"
    ):
        for obj in page.get("Contents", []):
            if obj.get("Key", "").endswith(".json"):
                keys.append(obj["Key"])
    return keys


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rescore", action="store_true")
    args = parser.parse_args()
    if not args.apply and not args.dry_run:
        parser.error("pass --dry-run or --apply")
    asyncio.run(main(apply=args.apply, rescore=args.rescore))
