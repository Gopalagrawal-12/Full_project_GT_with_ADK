"""
tools/vector_search_tool.py
------------------------------
Pure infrastructure tool: embeds the query and runs a cosine-similarity
search against `chunks` (pgvector). Wired into `vector_retrieval_agent` as a
FunctionTool, mirroring how `execute_sql` is wired into `query_execution_agent`
-- same error-string convention ("RETRIEVAL_ERROR: ...") so `check_fallback`
can branch on it identically.

Retrieval quality, not just similarity order:
  - Over-fetches (top_k * OVER_FETCH_FACTOR) candidates, then applies a
    minimum-similarity floor so near-irrelevant chunks never reach synthesis
    -- both a quality filter and a context-window control (fewer, more
    relevant chunks means less token spend in vector_synthesis_agent).
  - Caps results per source document (MAX_PER_DOCUMENT) so one large,
    heavily-matching document can't crowd out every other source -- keeps
    the final set diverse when the corpus has multiple ingested documents.
"""

from __future__ import annotations

import json
import logging
import time

import asyncpg

from tools.embedder import create_embedder
from utils.db_pool import get_pool

logger = logging.getLogger("adk_rag.tools.vector_search_tool")

# Module-level singleton: one embedder (and its query cache) shared across
# every retrieval call in this process.
_embedder = None

_OVER_FETCH_FACTOR = 4
_DEFAULT_MIN_SIMILARITY = 0.2
_MAX_PER_DOCUMENT = 3


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = create_embedder()
    return _embedder


async def vector_search(
    query: str,
    top_k: int = 5,
    dataset_label: str | None = None,
    min_similarity: float = _DEFAULT_MIN_SIMILARITY,
) -> str:
    """
    Embeds `query`, over-fetches candidates by cosine similarity, then
    filters/diversifies down to the `top_k` most relevant AND distinct
    results before returning them as a JSON-serializable string, joined with
    their parent document's title/source for citation.

    On any failure (embedding backend unreachable, pgvector not installed,
    etc.) this returns "RETRIEVAL_ERROR: <message>" instead of raising, so
    the calling agent can branch to `external_support` cleanly.
    """
    if not query or not query.strip():
        return "RETRIEVAL_ERROR: Empty query."

    top_k = max(1, min(top_k, 25))  # sane bounds regardless of what the LLM passes
    fetch_limit = top_k * _OVER_FETCH_FACTOR

    try:
        embedder = _get_embedder()
        query_embedding = await embedder.embed_query(query)
    except Exception as exc:  # noqa: BLE001
        logger.exception("vector_search: failed to embed query")
        return f"RETRIEVAL_ERROR: Could not generate query embedding ({exc})"

    embedding_literal = "[" + ",".join(map(str, query_embedding)) + "]"

    pool = await get_pool()
    start = time.perf_counter()
    try:
        async with pool.acquire() as conn:
            base_query = """
                SELECT
                    c.content,
                    c.metadata,
                    c.chunk_index,
                    d.id AS document_id,
                    d.title,
                    d.source,
                    1 - (c.embedding <=> $1::vector) AS similarity
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                {label_filter}
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
            """
            if dataset_label:
                records = await conn.fetch(
                    base_query.format(label_filter="WHERE d.dataset_label = $3"),
                    embedding_literal, fetch_limit, dataset_label,
                )
            else:
                records = await conn.fetch(
                    base_query.format(label_filter=""), embedding_literal, fetch_limit,
                )
    except asyncpg.PostgresError as exc:
        logger.warning("vector_search query failed: %s", exc)
        return f"RETRIEVAL_ERROR: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("vector_search unexpected failure")
        return f"RETRIEVAL_ERROR: {exc}"

    # Quality filter + per-document diversity cap, applied in similarity order.
    per_document_count: dict[str, int] = {}
    filtered: list[dict] = []
    for r in records:
        similarity = float(r["similarity"])
        if similarity < min_similarity:
            continue
        doc_id = str(r["document_id"])
        if per_document_count.get(doc_id, 0) >= _MAX_PER_DOCUMENT:
            continue
        per_document_count[doc_id] = per_document_count.get(doc_id, 0) + 1
        filtered.append(
            {
                "content": r["content"],
                "title": r["title"],
                "source": r["source"],
                "chunk_index": r["chunk_index"],
                "similarity": round(similarity, 4),
                "metadata": r["metadata"],
            }
        )
        if len(filtered) >= top_k:
            break

    elapsed_ms = (time.perf_counter() - start) * 1000
    return json.dumps(
        {"success": True, "result_count": len(filtered), "elapsed_ms": round(elapsed_ms, 2), "results": filtered},
        default=str,
    )
