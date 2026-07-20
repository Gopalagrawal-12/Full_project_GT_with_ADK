"""
agents/query_review_agent.py
--------------------------------
Agent 5 of 10. Audits `generated_sql` for correctness and numeric-precision
safety before it ever touches the database. Writes `ctx.state["reviewed_sql"]`.

Needs only the SQL itself -- no schema access. Structural/precision review
(ROUND wrapping, NOT NULL guards, single-statement, read-only) doesn't
require re-grounding in column semantics; query_generation_agent already had
the detailed metadata when it wrote the query.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-flash-latest")

query_review_agent = Agent(
    name="query_review",
    model=_MODEL,
    description="Audits generated SQL for correctness and numeric-precision safety.",
    include_contents="none",
    instruction=(
        "GENERATED SQL:\n{generated_sql}\n\n"
        "Audit it and return the corrected, final single-statement SQL only (no prose, "
        "no fences, no trailing semicolon).\n\n"
        "Enforce:\n"
        "- Every float/numeric arithmetic result and every comparison involving division "
        "  must be wrapped in ROUND(..., 2) to eliminate floating-point precision drift.\n"
        "- Confirm NOT NULL guards on JSONB entity extractions are present; add them if "
        "  missing.\n"
        "- Confirm the query is read-only and single-statement; strip any trailing "
        "  semicolon.\n"
        "- Do not change the semantic intent of the query, only correctness/formatting."
    ),
    output_key="reviewed_sql",
)
