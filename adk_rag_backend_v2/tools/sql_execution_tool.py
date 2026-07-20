"""
tools/sql_execution_tool.py
------------------------------
Pure infrastructure tool: executes a single, read-only SQL statement against
`data_rows` / `file_metadata` via the shared asyncpg pool. Wired into the
`query_execution` agent as a `FunctionTool` in agents/query_execution_agent.py.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import asyncpg

from utils.db_pool import get_pool

logger = logging.getLogger("adk_rag.tools.sql_execution_tool")

# Hard safety rails: this tool must never be allowed to mutate data.
_FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "truncate",
    "grant", "revoke", "create", "commit", "rollback",
)


async def execute_sql(query: str) -> str:
    """
    Executes a single, read-only SQL statement and returns a JSON-serializable
    string.

    Contract with query_generation/query_review:
      - Exactly one statement, no trailing semicolon.
      - Read-only: any DML/DDL keyword is rejected before it ever reaches asyncpg.

    On any failure (syntax error, permission error, runtime error) this
    returns the literal string "EXECUTION_ERROR: <message>" instead of
    raising, so the calling agent can branch to `external_support` cleanly.
    """
    normalized = query.strip().rstrip(";")
    lowered = normalized.lower()

    if not lowered.startswith(("select", "with")):
        return "EXECUTION_ERROR: Only read-only SELECT/CTE statements are permitted."

    if any(f" {kw} " in f" {lowered} " for kw in _FORBIDDEN_KEYWORDS):
        return "EXECUTION_ERROR: Query contains a forbidden mutating keyword."

    pool = await get_pool()
    start = time.perf_counter()
    try:
        async with pool.acquire() as conn:
            # Belt-and-suspenders: pin the transaction to read-only at the DB level.
            async with conn.transaction(readonly=True):
                records = await conn.fetch(normalized)
    except (asyncpg.PostgresSyntaxError, asyncpg.PostgresError) as exc:
        logger.warning("execute_sql runtime/syntax error: %s", exc)
        return f"EXECUTION_ERROR: {exc}"
    except Exception as exc:  # noqa: BLE001 - must never raise into the agent runtime
        logger.exception("execute_sql unexpected failure")
        return f"EXECUTION_ERROR: {exc}"

    elapsed_ms = (time.perf_counter() - start) * 1000
    rows: list[dict[str, Any]] = [dict(r) for r in records]

    return json.dumps(
        {
            "success": True,
            "row_count": len(rows),
            "elapsed_ms": round(elapsed_ms, 2),
            "rows": rows,
        },
        default=str,  # safely stringify Decimal/datetime/etc. from JSONB casts
    )
