"""
utils/providers.py
---------------------
Central place that decides which embedding backend the vector pipeline talks
to. Defaults to a local Ollama instance (OpenAI-compatible `/v1` API), which
keeps this project runnable with zero cloud credentials — swap the three env
vars below to point at OpenAI, Azure OpenAI, or any other OpenAI-compatible
embeddings endpoint without touching any other file.
"""

from __future__ import annotations

import os
import logging
from openai import AsyncOpenAI

# Import the API Key Pool you created earlier
from utils.api_pool import AsyncAPIKeyPool

logger = logging.getLogger("adk_rag.utils.providers")

_EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434/v1")
_EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "ollama")
_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# nomic-embed-text = 768 dims. Override if you switch models (e.g.
# text-embedding-3-small = 1536). This value also sizes the pgvector column,
# so changing it requires re-running the schema bootstrap against a fresh table.
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))

_client: AsyncOpenAI | None = None


def get_embedding_client() -> AsyncOpenAI:
    """Returns a shared AsyncOpenAI client pointed at the configured embedding backend."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=_EMBEDDING_BASE_URL, api_key=_EMBEDDING_API_KEY)
    return _client


def get_embedding_model() -> str:
    return _EMBEDDING_MODEL


# --------------------------------------------------------------------------- #
# Groq client: used at ingestion time to auto-generate rich column metadata.
# Transparently wrapped with AsyncAPIKeyPool to cycle through multiple keys.
# --------------------------------------------------------------------------- #

_METADATA_MODEL = os.getenv("GROQ_METADATA_MODEL", "llama-3.1-8b-instant")
_groq_client = None


class PooledGroqClient:
    """
    A transparent wrapper that mimics the AsyncGroq SDK structure but
    routes all LLM calls through the AsyncAPIKeyPool to handle 429s.
    """
    def __init__(self, pool: AsyncAPIKeyPool):
        self.pool = pool
        self.chat = self._Chat(pool)

    class _Chat:
        def __init__(self, pool):
            self.completions = self._Completions(pool)

        class _Completions:
            def __init__(self, pool):
                self.pool = pool

            async def create(self, **kwargs):
                async def _do_call(active_key: str):
                    from groq import AsyncGroq
                    # Create a lightweight temporary client with the active key
                    temp_client = AsyncGroq(api_key=active_key)
                    # Pass all arguments (model, messages, temperature, etc.) exactly as received
                    return await temp_client.chat.completions.create(**kwargs)

                # Execute using the pool to catch 429 RateLimitErrors and cycle keys
                return await self.pool.execute(_do_call)


def get_groq_client():
    """Returns a PooledGroqClient that automatically rotates through available Groq API keys."""
    global _groq_client
    if _groq_client is None:
        # 1. Collect all Groq keys from the environment
        groq_keys = []

        # Check standard key
        if os.getenv("GROQ_API_KEY"):
            groq_keys.append(os.getenv("GROQ_API_KEY"))

        # Check numbered keys (GROQ_API_KEY_1, GROQ_API_KEY_2, etc.) up to 10
        for i in range(1, 11):
            key = os.getenv(f"GROQ_API_KEY_{i}")
            if key and key not in groq_keys:
                groq_keys.append(key)

        if not groq_keys:
            logger.warning("No GROQ_API_KEY found in environment. Ingestion metadata may fail.")
            groq_keys = ["dummy_key_to_allow_boot"]

        # 2. Initialize the pool and wrap it
        groq_pool = AsyncAPIKeyPool(groq_keys)
        _groq_client = PooledGroqClient(groq_pool)

        logger.info(f"Initialized Groq pool with {len(groq_keys)} API keys.")

    return _groq_client


def get_metadata_model() -> str:
    return _METADATA_MODEL