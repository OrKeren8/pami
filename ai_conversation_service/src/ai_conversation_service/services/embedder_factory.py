from loguru import logger
from openai import AsyncOpenAI

from ai_conversation_service.core.config import settings
from ai_conversation_service.services.embedder import LocalOnnxEmbedder, OpenAiEmbedder


async def build_embedder():
    """Prefer the configured provider, fall back to the local model, then to nothing.

    The provider is decided once per process and its model id is stored on every chunk, so a
    mid-flight switch cannot mix two vector spaces within one conversation's index state.

    Lives here rather than in main so anything that has to reproduce production vectors -
    the calibration measurement in particular - embeds with the same model the service does
    instead of a hardcoded second choice.
    """
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        try:
            embedder = OpenAiEmbedder(
                AsyncOpenAI(api_key=settings.openai_api_key),
                settings.openai_embedding_model,
            )
            await embedder.probe()
            return embedder
        except Exception as error:
            logger.error(
                f"OpenAI embeddings unavailable ({type(error).__name__}: {error}); "
                f"falling back to the local model"
            )

    try:
        return LocalOnnxEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    except Exception as error:
        logger.error(
            f"Embedder unavailable ({type(error).__name__}); "
            f"cross-conversation retrieval is disabled"
        )
        return None
