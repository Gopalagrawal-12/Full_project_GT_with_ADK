"""
agents/query_generation_agent.py
------------------------------------
Agent 4 of 10. Generates a single PostgreSQL statement joining `data_rows d`
and `file_metadata m`. Writes `ctx.state["generated_sql"]`.

This is the one agent that gets the EXPENSIVE, fully-detailed column
metadata -- `{db_schema_detail}`, produced by
`services.graph_nodes.load_relevant_schema_detail` right before this node
runs, already filtered to the entities/metrics `query_understanding`
extracted. It includes, per relevant column: a semantic description, known
synonyms/jargon, and sql_hints (casting/formatting/filtering rules) --
generated from real sample data at ingestion time by
`api.ingest_routes.generate_column_metadata` (Groq). Trust these over
guessing from a bare column name.

Mandatory laws baked into the instruction (do not weaken these):
  1. Always join as: FROM data_rows d JOIN file_metadata m ON d.file_id = m.id
  2. Exclude blank/null entities via IS NOT NULL checks (Excel summary-row trap).
  3. Wrap JSONB numeric extraction in parens before casting:
     SUM((d.row_data->>'Key')::numeric)
  4. Single-statement query blocks only, no trailing semicolon (asyncpg).
  5. Fold in the time-series CTE hint when present.
  6. Read-only: SELECT/CTE only, never DML/DDL.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-flash-latest")

query_generation_agent = Agent(
    name="query_generation",
    model=_MODEL,
    description="Generates a single PostgreSQL statement against data_rows/file_metadata.",
    include_contents="none",
    instruction=(
        "PARSED INTENT:\n{parsed_intent}\n\n"
        "RELEVANT COLUMN METADATA (generated from real sample data -- trust it over "
        "guessing from a column name alone; match the user's terminology to a column "
        "via its listed synonyms before falling back to a literal name match):\n"
        "{db_schema_detail}\n\n"
        "TIME-SERIES GUIDANCE:\n{time_series_hint}\n\n"
        "You generate exactly ONE PostgreSQL SELECT/CTE statement and nothing else "
        "(no markdown fences, no trailing semicolon, no commentary).\n\n"
        "MANDATORY LAWS (violating any of these is a hard failure):\n"
        "1. Always join as: FROM data_rows d JOIN file_metadata m ON d.file_id = m.id\n"
        "2. Every entity/dimension pulled from JSONB must have an explicit "
        "   `d.row_data->>'Key' IS NOT NULL` guard to exclude blank/null rows and "
        "   Excel-style summary/subtotal rows.\n"
        "3. Wrap every JSONB numeric extraction in parentheses before casting, e.g. "
        "   SUM((d.row_data->>'Revenue')::numeric) -- never cast without the parens.\n"
        "4. Output a single statement block only. NEVER emit a trailing semicolon "
        "   (asyncpg's fetch() rejects multi-statement bodies).\n"
        "5. If the time-series guidance above is not 'NONE', structure the query using "
        "   the suggested CTE shape.\n"
        "6. Never emit INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE -- SELECT/CTE only."
    ),
    output_key="generated_sql",
)
