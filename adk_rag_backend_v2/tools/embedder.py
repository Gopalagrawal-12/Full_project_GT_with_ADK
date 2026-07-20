"""
tools/embedder.py
--------------------
Generates embeddings for document chunks via an OpenAI-compatible client
(defaults to local Ollama — see utils/providers.py). Ollama's embeddings
endpoint takes one input per request, so batches are fanned out with bounded
concurrency rather than relying on a multi-input batch call.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from openai import APIConnectionError, APIError

from tools.chunker import DocumentChunk
from utils.providers import EMBEDDING_DIMENSION, get_embedding_client, get_embedding_model

logger = logging.getLogger("adk_rag.tools.embedder")


class EmbeddingGenerator:
    """Generates embeddings for text / document chunks, with retries and bounded concurrency."""

    def __init__(
        self,
        model: Optional[str] = None,
        dimension: int = EMBEDDING_DIMENSION,
        concurrency: int = 8,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.model = model or get_embedding_model()
        self.dimension = dimension
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = get_embedding_client()
        self._semaphore = asyncio.Semaphore(concurrency)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding for a single text, with exponential-backoff retries."""
        if not text or not text.strip():
            return [0.0] * self.dimension

        async with self._semaphore:
            last_exc: Exception | None = None
            for attempt in range(self.max_retries):
                try:
                    response = await self._client.embeddings.create(model=self.model, input=text)
                    return response.data[0].embedding
                except APIConnectionError as exc:
                    last_exc = exc
                    if attempt == self.max_retries - 1:
                        logger.error(
                            "Cannot reach the embedding backend after %d attempts. "
                            "Is it running and has `%s` been pulled/deployed?",
                            self.max_retries, self.model,
                        )
                        raise
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                except APIError as exc:
                    last_exc = exc
                    logger.error("Embedding API error: %s", exc)
                    if attempt == self.max_retries - 1:
                        raise
                    await asyncio.sleep(self.retry_delay)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    logger.error("Unexpected error generating embedding: %s", exc)
                    if attempt == self.max_retries - 1:
                        raise
                    await asyncio.sleep(self.retry_delay)
            # Unreachable in practice (loop always returns or raises), kept for type-checkers.
            raise last_exc or RuntimeError("Embedding generation failed with no captured exception.")

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for many texts concurrently (bounded by the semaphore)."""
        results = await asyncio.gather(
            *(self.generate_embedding(t) for t in texts), return_exceptions=True
        )
        embeddings: list[list[float]] = []
        for text, result in zip(texts, results):
            if isinstance(result, Exception):
                logger.error("Failed to embed text (using zero vector): %s", result)
                embeddings.append([0.0] * self.dimension)
            else:
                embeddings.append(result)
        return embeddings

    async def embed_chunks(
        self,
        chunks: list[DocumentChunk],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        batch_size: int = 32,
    ) -> list[DocumentChunk]:
        """Generate + attach embeddings to a list of DocumentChunk, processed in batches."""
        if not chunks:
            return chunks

        logger.info("Generating embeddings for %d chunks with %s", len(chunks), self.model)
        embedded: list[DocumentChunk] = []
        total_batches = (len(chunks) + batch_size - 1) // batch_size

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = await self.generate_embeddings_batch([c.content for c in batch])

            for chunk, embedding in zip(batch, embeddings):
                chunk.metadata.update(
                    {"embedding_model": self.model, "embedding_generated_at": datetime.now(timezone.utc).isoformat()}
                )
                chunk.embedding = embedding
                embedded.append(chunk)

            batch_num = (i // batch_size) + 1
            if progress_callback:
                progress_callback(batch_num, total_batches)
            logger.info("Embedded batch %d/%d", batch_num, total_batches)

        return embedded

    async def embed_query(self, query: str) -> list[float]:
        """Generate an embedding for a search query (same model as document chunks)."""
        return await self.generate_embedding(query)

    def get_embedding_dimension(self) -> int:
        return self.dimension


class EmbeddingCache:
    """Small in-memory LRU-ish cache — mainly useful for repeated identical queries."""

    def __init__(self, max_size: int = 2000):
        self.cache: dict[str, list[float]] = {}
        self.access_times: dict[str, datetime] = {}
        self.max_size = max_size

    def get(self, text: str) -> Optional[list[float]]:
        key = self._hash(text)
        if key in self.cache:
            self.access_times[key] = datetime.now(timezone.utc)
            return self.cache[key]
        return None

    def put(self, text: str, embedding: list[float]) -> None:
        key = self._hash(text)
        if len(self.cache) >= self.max_size:
            oldest = min(self.access_times, key=self.access_times.get)
            del self.cache[oldest]
            del self.access_times[oldest]
        self.cache[key] = embedding
        self.access_times[key] = datetime.now(timezone.utc)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()


def create_embedder(model: Optional[str] = None, use_cache: bool = True, **kwargs) -> EmbeddingGenerator:
    """Factory: creates an EmbeddingGenerator, optionally wrapped with a query cache."""
    embedder = EmbeddingGenerator(model=model, **kwargs)

    if use_cache:
        cache = EmbeddingCache()
        original = embedder.generate_embedding

        async def cached_generate(text: str) -> list[float]:
            cached = cache.get(text)
            if cached is not None:
                return cached
            embedding = await original(text)
            cache.put(text, embedding)
            return embedding

        embedder.generate_embedding = cached_generate  # type: ignore[method-assign]

    return embedder
