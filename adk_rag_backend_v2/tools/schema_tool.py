"""
tools/schema_tool.py
----------------------
Two-tier schema grounding, so every agent gets exactly the context it needs
and nothing more (see services/graph_nodes.py for who calls what, and when):

  fetch_schema_overview()          CHEAP. Table/document names, row counts,
                                    column NAMES only, one-line table
                                    summaries. Enough for query_understanding
                                    to map user language to real tables/
                                    columns and for query_classification to
                                    decide SQL vs VECTOR -- neither needs full
                                    per-column descriptions to do that.

  fetch_schema_relevant_detail(..)  EXPENSIVE (verbose). Full LLM-generated
                                    column metadata (description, synonyms,
                                    sql_hints) -- but ONLY for columns that
                                    actually match the entities/metrics the
                                    question is about. Every other column
                                    gets a one-line name+hint stub. This is
                                    what query_generation_agent needs to
                                    write correct SQL, without paying the
                                    token cost of every column of every
                                    ingested table on every single question.

Both read `file_metadata.columns`, which is the rich shape produced by
`api.ingest_routes.generate_column_metadata` (Groq) --
{"table_summary": str, "columns": {name: {description, synonyms, sql_hints}}} --
with a graceful fallback for the legacy/failure shape {name: dtype}.
"""

from __future__ import annotations

import logging

import asyncpg
import json
from utils.db_pool import get_pool

logger = logging.getLogger("adk_rag.tools.schema_tool")


def _column_names(raw_columns: dict) -> list[str]:
    if not isinstance(raw_columns, dict):
        return []
    if "columns" in raw_columns and isinstance(raw_columns["columns"], dict):
        return list(raw_columns["columns"].keys())
    return list(raw_columns.keys())  # legacy {name: dtype} shape


def _table_summary(raw_columns: dict) -> str:
    if isinstance(raw_columns, dict) and isinstance(raw_columns.get("table_summary"), str):
        return raw_columns["table_summary"]
    return ""


async def fetch_schema_overview() -> str:
    """Cheap grounding: table/column NAMES + one-line summaries. Used broadly."""
    pool = await get_pool()
    sections: list[str] = []

    try:
        async with pool.acquire() as conn:
            tabular_records = await conn.fetch(
                "SELECT id, file_name, dataset_label, columns, row_count FROM file_metadata ORDER BY ingested_at DESC"
            )
    except asyncpg.PostgresError as exc:
        logger.exception("fetch_schema_overview: tabular query failed")
        tabular_records = None
        sections.append(f"TABULAR DATA LAKE: unavailable (SCHEMA_FETCH_ERROR: {exc})")

    if tabular_records is not None:
        if not tabular_records:
            sections.append("TABULAR DATA LAKE: no datasets ingested yet.")
        else:
            lines = []
            for r in tabular_records:
                raw_columns = r["columns"] or {}
                names = ", ".join(_column_names(raw_columns)) or "unknown"
                summary = _table_summary(raw_columns)
                line = (
                    f"- file_id={r['id']} | \"{r['file_name']}\" (label: {r['dataset_label'] or 'n/a'}) "
                    f"| rows={r['row_count']} | columns: {names}"
                )
                if summary:
                    line += f" | summary: {summary}"
                lines.append(line)
            sections.append(
                "TABULAR DATA LAKE (SQL branch; join data_rows d ON d.file_id = m.id):\n" + "\n".join(lines)
            )

    try:
        async with pool.acquire() as conn:
            doc_records = await conn.fetch(
                """
                SELECT dataset_label, COUNT(*) AS doc_count, array_agg(DISTINCT title) AS titles
                FROM documents GROUP BY dataset_label ORDER BY doc_count DESC
                """
            )
    except asyncpg.PostgresError as exc:
        logger.warning("fetch_schema_overview: document query failed (pgvector likely unavailable): %s", exc)
        doc_records = None
        sections.append("DOCUMENT CORPUS: unavailable (vector store not initialized).")

    if doc_records is not None:
        if not doc_records:
            sections.append("DOCUMENT CORPUS: no documents ingested yet.")
        else:
            lines = [
                f"- label: {r['dataset_label'] or 'n/a'} | documents={r['doc_count']} | "
                f"e.g. {', '.join((r['titles'] or [])[:5])}"
                for r in doc_records
            ]
            sections.append("DOCUMENT CORPUS (VECTOR branch, via vector_search):\n" + "\n".join(lines))

    return "\n\n".join(sections) if sections else "No data has been ingested yet in either the tabular or document store."


async def fetch_schema_relevant_detail(entities: list[str], metrics: list[str], aliases: dict) -> str:
    """
    Verbose grounding for query_generation_agent ONLY. Full per-column
    description/synonyms/sql_hints for columns matching the question's
    entities/metrics/aliases (case-insensitive substring match against the
    column name, its description, or its synonyms); every other column is
    reduced to a one-line stub so joins/filters on unmentioned columns are
    still *possible* without spending tokens describing them in full.

    If nothing matches (e.g. a very open-ended question, or metadata
    generation never ran for a table), falls back to full detail so
    query_generation still has something concrete to work from.
    """
    keywords = {k.strip().lower() for k in (entities + metrics + list(aliases.keys()) + list(aliases.values())) if k and k.strip()}

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT id, file_name, dataset_label, columns, row_count FROM file_metadata ORDER BY ingested_at DESC"
            )
    except asyncpg.PostgresError as exc:
        logger.exception("fetch_schema_relevant_detail failed")
        return f"SCHEMA_FETCH_ERROR: {exc}"

    if not records:
        return "No tabular datasets have been ingested yet."

    lines: list[str] = []
    for r in records:
        raw_columns = r["columns"] or {}
        lines.append(
            f"- file_id={r['id']} | \"{r['file_name']}\" (label: {r['dataset_label'] or 'n/a'}) | rows={r['row_count']}"
        )
        summary = _table_summary(raw_columns)
        if summary:
            lines.append(f"  table_summary: {summary}")

        columns_map = raw_columns.get("columns") if isinstance(raw_columns, dict) else None
        if not isinstance(columns_map, dict) or not columns_map:
            # Legacy/fallback shape -- no rich metadata to filter, show as-is.
            if isinstance(raw_columns, str):
                try:
                    raw_columns = json.loads(raw_columns)
                except json.JSONDecodeError:
                    raw_columns = {}  # Fallback to empty dict if parsing fails

                # Your original line that was crashing:
            lines.append("  columns: " + ", ".join(f"{n} ({d})" for n, d in raw_columns.items()))
            continue

        for name, meta in columns_map.items():
            if not isinstance(meta, dict):
                lines.append(f"  - {name}: {meta}")
                continue

            desc = meta.get("description") or ""
            synonyms = meta.get("synonyms") or []
            hints = meta.get("sql_hints") or ""
            haystack = f"{name} {desc} {' '.join(synonyms)}".lower()
            is_relevant = not keywords or any(kw in haystack for kw in keywords)

            if is_relevant:
                bits = [f"  - {name}"]
                if desc:
                    bits.append(f": {desc}")
                if synonyms:
                    bits.append(f" (aka: {', '.join(synonyms)})")
                if hints:
                    bits.append(f" [sql_hints: {hints}]")
                lines.append("".join(bits))
            else:
                # Unmatched column: keep it queryable (name + hint) without the token cost of description/synonyms.
                stub = f"  - {name}"
                if hints:
                    stub += f" [sql_hints: {hints}]"
                lines.append(stub)

    return "\n".join(lines)
