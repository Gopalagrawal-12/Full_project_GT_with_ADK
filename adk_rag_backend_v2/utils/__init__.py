"""
utils package
---------------
- db_pool.py               asyncpg connection pool lifecycle
- db_schema_bootstrap.py   idempotent DDL for both the tabular data lake
                            (file_metadata/data_rows) and the vector store
                            (documents/chunks + pgvector)
- providers.py             embedding backend (Ollama by default) + Groq
                            client config (auto column-metadata generation)
"""

from utils.db_pool import close_pool, get_pool, init_pool
from utils.db_schema_bootstrap import ensure_schema
from utils.providers import (
    EMBEDDING_DIMENSION,
    get_embedding_client,
    get_embedding_model,
    get_groq_client,
    get_metadata_model,
)

__all__ = [
    "init_pool",
    "close_pool",
    "get_pool",
    "ensure_schema",
    "get_embedding_client",
    "get_embedding_model",
    "EMBEDDING_DIMENSION",
    "get_groq_client",
    "get_metadata_model",
]
