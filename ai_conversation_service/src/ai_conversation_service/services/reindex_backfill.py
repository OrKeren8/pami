from loguru import logger

from ai_conversation_service.data.vector_index import CHUNK_COLLECTION

_logger = logger.bind(service="ReindexBackfill")


async def reindex_stale_conversations(
    database,
    chunk_index_service,
    transcripts,
    limit: int,
) -> int:
    """Re-embed conversations still indexed with an older embedding model.

    Changing the embedding model does not rewrite what is already stored, and vectors of
    different widths cannot be compared - the width guard in retrieval skips them. Without
    this, switching models silently hid every conversation recorded before the switch:
    retrieval kept working, returned nothing from the history, and the assistant answered
    that it had no record of things the user had definitely told it.

    Runs in the background at startup and is a no-op once everything matches, so the cost
    is paid once per model change rather than on every boot.
    """
    if not chunk_index_service or not transcripts:
        return 0

    current_model = chunk_index_service.embedding_model
    if not current_model:
        return 0

    stale_ids = await database[CHUNK_COLLECTION].distinct(
        "conversation_id", {"embedding_model": {"$ne": current_model}}
    )
    if not stale_ids:
        _logger.info(f"All indexed chunks are on {current_model}; nothing to backfill")
        return 0

    _logger.warning(
        f"{len(stale_ids)} conversation(s) are indexed with a model other than "
        f"{current_model} and are invisible to retrieval; re-indexing up to {limit}"
    )

    reindexed = 0
    for conversation_id in stale_ids[:limit]:
        try:
            conversation = await transcripts.get_conversation(conversation_id)
            if not conversation or not getattr(conversation, "messages", None):
                # The transcript is gone but its chunks are not. Leaving them would keep
                # this backfill reporting work it can never do.
                await database[CHUNK_COLLECTION].delete_many(
                    {"conversation_id": conversation_id}
                )
                _logger.info(
                    f"Dropped chunks for {conversation_id}: no transcript to re-index"
                )
                continue

            await chunk_index_service.reindex_conversation(
                conversation_id,
                conversation.project_id,
                getattr(conversation, "context_node_id", None),
                conversation.messages,
                getattr(conversation, "title", None),
            )
            reindexed += 1
        except Exception as error:
            # One unreadable conversation must not stop the rest from becoming searchable.
            _logger.error(
                f"Could not re-index {conversation_id} "
                f"({type(error).__name__}: {error})"
            )

    remaining = len(stale_ids) - min(len(stale_ids), limit)
    _logger.info(
        f"Backfill re-indexed {reindexed} conversation(s) onto {current_model}"
        + (f"; {remaining} left for the next start" if remaining else "")
    )
    return reindexed
