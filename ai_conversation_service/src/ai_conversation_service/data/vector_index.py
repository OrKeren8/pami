from loguru import logger
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

VECTOR_INDEX_NAME = "conversation_chunk_vectors"
CHUNK_COLLECTION = "conversation_chunks"

_logger = logger.bind(component="vector_index")


async def ensure_vector_index(database: AsyncDatabase, dimensions: int) -> bool:
    """Create the Atlas vector-search index for conversation chunks if absent."""
    collection = database[CHUNK_COLLECTION]

    try:
        cursor = await collection.list_search_indexes()
        existing = await cursor.to_list()
    except OperationFailure as error:
        _logger.warning(
            f"Atlas search indexes unsupported on this cluster "
            f"(code {error.code}); vector retrieval will be disabled"
        )
        return False

    for index in existing:
        if index.get("name") != VECTOR_INDEX_NAME:
            continue
        if _dimensions_of(index) != dimensions:
            _logger.error(
                f"Vector index {VECTOR_INDEX_NAME} has "
                f"{_dimensions_of(index)} dimensions but the embedder produces "
                f"{dimensions}; drop the index to rebuild it"
            )
            return False
        return True

    try:
        await collection.create_search_index(
            SearchIndexModel(
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": dimensions,
                            "similarity": "cosine",
                        },
                        {"type": "filter", "path": "project_id"},
                        {"type": "filter", "path": "conversation_id"},
                    ]
                },
                name=VECTOR_INDEX_NAME,
                type="vectorSearch",
            )
        )
    except OperationFailure as error:
        _logger.error(
            f"Failed to create vector index {VECTOR_INDEX_NAME}: "
            f"{type(error).__name__} (code {error.code})"
        )
        return False

    _logger.info(
        f"Created vector index {VECTOR_INDEX_NAME} ({dimensions} dims); "
        f"it becomes queryable asynchronously"
    )
    return True


def _dimensions_of(index: dict) -> int | None:
    for field in index.get("latestDefinition", {}).get("fields", []):
        if field.get("type") == "vector":
            return field.get("numDimensions")
    return None
