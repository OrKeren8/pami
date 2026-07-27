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
