"""
utils/db_pool.py
-------------------
Global asyncpg connection pool manager. A single pool is created during the
FastAPI lifespan and shared by every request; nothing in this codebase should
ever call `asyncpg.connect()` directly.
"""

from __future__ import annotations

import logging
import os

import asyncpg

logger = logging.getLogger("adk_rag.utils.db_pool")

_pool: asyncpg.Pool | None = None

# Safe environment-variable fallbacks. In production these should always come
# from the environment / secret manager, never hardcoded.
_PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
_PG_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
_PG_DB = os.getenv("POSTGRES_DB", "ragdb1")
_PG_USER = os.getenv("POSTGRES_USER", "gopal")
_PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "ragpassword")
_PG_MIN_POOL_SIZE = int(os.getenv("POSTGRES_MIN_POOL_SIZE", "2"))
_PG_MAX_POOL_SIZE = int(os.getenv("POSTGRES_MAX_POOL_SIZE", "10"))
_PG_COMMAND_TIMEOUT = float(os.getenv("POSTGRES_COMMAND_TIMEOUT", "30"))


async def init_pool() -> asyncpg.Pool:
    """Creates the global pool. Call exactly once, from the FastAPI lifespan."""
    global _pool
    if _pool is not None:
        logger.warning("init_pool called but a pool already exists; reusing it.")
        return _pool

    logger.info(
        "Creating asyncpg pool -> host=%s db=%s min=%d max=%d",
        _PG_HOST, _PG_DB, _PG_MIN_POOL_SIZE, _PG_MAX_POOL_SIZE,
    )
    _pool = await asyncpg.create_pool(
        host=_PG_HOST,
        port=_PG_PORT,
        database=_PG_DB,
        user=_PG_USER,
        password=_PG_PASSWORD,
        min_size=_PG_MIN_POOL_SIZE,
        max_size=_PG_MAX_POOL_SIZE,
        command_timeout=_PG_COMMAND_TIMEOUT,
    )
    return _pool


async def close_pool() -> None:
    """Gracefully closes the global pool. Call from the FastAPI lifespan shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed.")


async def get_pool() -> asyncpg.Pool:
    """
    Returns the live pool. Tools call this instead of holding their own
    reference, so a single init_pool()/close_pool() cycle in main.py governs
    the whole app's DB lifecycle.
    """
    if _pool is None:
        raise RuntimeError(
            "Connection pool is not initialized. Ensure the FastAPI lifespan "
            "context manager has run init_pool() before handling requests."
        )
    return _pool
