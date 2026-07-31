import asyncio
from typing import Protocol

from fastembed import TextEmbedding
from loguru import logger


class Embedder(Protocol):
    """Turns text into dense vectors for similarity search."""

    dimensions: int
    model_id: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalOnnxEmbedder:
    """Embeds text in-process with a quantized ONNX sentence-transformer."""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        self._logger = logger.bind(service="LocalOnnxEmbedder")
        self._model_name = model_name
        self._model = TextEmbedding(model_name, cache_dir=cache_dir or None)
        self.dimensions = len(self._embed_sync(["dimension probe"])[0])
        self.model_id = f"{model_name.split('/')[-1]}@{self.dimensions}"
        self._logger.info(f"Loaded embedder {self.model_id}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts off the event loop, since ONNX inference is CPU-bound."""
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]


class OpenAiEmbedder:
    """Embeds text with OpenAI's embedding API.

    Measured against the local 384-dimension model on this project's own data: asking "what
    are my dogs called?" ranked the chunk holding the answer 4th of 41 locally, below
    unrelated project chunks (0.52 against 0.67), because every conversation in one project
    shares its vocabulary and the small model saturates. The same query with
    text-embedding-3-small ranks the answer 1st of 106 at 0.709 with the best irrelevant
    chunk at 0.667 - the ordering that retrieval depends on.
    """

    BATCH_SIZE = 64

    def __init__(self, client, model: str):
        self._logger = logger.bind(service="OpenAiEmbedder")
        self._client = client
        self._model = model
        self.dimensions = 0
        self.model_id = model

    async def probe(self) -> None:
        """Discover the vector width, and fail here rather than at first use."""
        vector = (await self.embed(["dimension probe"]))[0]
        self.dimensions = len(vector)
        self.model_id = f"{self._model}@{self.dimensions}"
        self._logger.info(f"Using embedder {self.model_id}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        # Batched because a reindex embeds every window of a conversation at once and the API
        # rejects oversized requests.
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start : start + self.BATCH_SIZE]
            response = await self._client.embeddings.create(
                model=self._model, input=batch
            )
            vectors.extend(item.embedding for item in response.data)
        return vectors
