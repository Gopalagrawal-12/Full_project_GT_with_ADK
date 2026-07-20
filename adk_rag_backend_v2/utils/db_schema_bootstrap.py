"""
utils/db_schema_bootstrap.py
--------------------------------
Idempotent DDL bootstrap for BOTH storage subsystems this backend runs:

  1. Tabular data lake (Text-to-SQL branch):  file_metadata, data_rows
  2. Vector document store (RAG branch):       documents, chunks (+ pgvector)

Kept separate from db_pool.py so "how do we connect" and "what tables must
exist" don't live in the same file.
"""

from __future__ import annotations

import logging

from utils.db_pool import get_pool
from utils.providers import EMBEDDING_DIMENSION

logger = logging.getLogger("adk_rag.utils.db_schema_bootstrap")

_TABULAR_DDL = """
CREATE TABLE IF NOT EXISTS file_metadata (
    id            SERIAL PRIMARY KEY,
    file_name     TEXT NOT NULL,
    dataset_label TEXT,
    columns       JSONB NOT NULL DEFAULT '{}'::jsonb,
    row_count     INTEGER NOT NULL DEFAULT 0,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_rows (
    id       BIGSERIAL PRIMARY KEY,
    file_id  INTEGER NOT NULL REFERENCES file_metadata(id) ON DELETE CASCADE,
    row_data JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_rows_file_id ON data_rows(file_id);
CREATE INDEX IF NOT EXISTS idx_data_rows_row_data_gin ON data_rows USING GIN (row_data);
"""

# EMBEDDING_DIMENSION is interpolated (not parameterized) because DDL can't
# bind params for a column type -- this value comes from an env var under our
# control (utils/providers.py), never from user input.
_VECTOR_DDL_TEMPLATE = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    source        TEXT NOT NULL,
    content       TEXT NOT NULL,
    dataset_label TEXT,
    metadata      JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content       TEXT NOT NULL,
    embedding     VECTOR({dim}),
    chunk_index   INTEGER NOT NULL,
    token_count   INTEGER,
    metadata      JSONB NOT NULL DEFAULT '{{}}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

-- IVFFlat requires an initial row estimate; harmless (and skipped) on an
-- empty table, and cheap to rebuild later with `REINDEX INDEX` as data grows.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chunks_embedding_ivfflat'
    ) THEN
        BEGIN
            CREATE INDEX idx_chunks_embedding_ivfflat
                ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping ivfflat index creation (likely an empty table): %', SQLERRM;
        END;
    END IF;
END $$;
"""


async def ensure_schema() -> None:
    """Idempotently creates every table (tabular + vector) if not already present."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(_TABULAR_DDL)
        try:
            await conn.execute(_VECTOR_DDL_TEMPLATE.format(dim=EMBEDDING_DIMENSION))
        except Exception as exc:  # noqa: BLE001
            # pgvector extension may not be installed on the target Postgres
            # instance. Fail soft: the SQL branch of the pipeline still works,
            # only the vector/RAG branch will error until `vector` is available.
            logger.warning(
                "Vector schema bootstrap failed (pgvector extension likely "
                "unavailable on this Postgres instance): %s", exc,
            )
    logger.info("Schema bootstrap complete.")
