"""
services/graph_nodes.py
--------------------------
Plain Python `@node` functions -- cheap glue between the 10 LLM agents. These
read/write `ctx.state` directly and, where used inside a RoutingMap edge,
their return value is the routing signal that selects the next branch.

  load_schema_context           -> cheap, ALWAYS-needed grounding (table/doc
                                    names, column names, one-line summaries).
                                    Runs once, before query_understanding.
  load_relevant_schema_detail   -> expensive, SQL-branch-only grounding:
                                    full column metadata, but filtered to
                                    state.parsed_intent's entities/metrics so
                                    query_generation isn't paying token cost
                                    for every column of every ingested table
                                    on every question. Runs only after
                                    parsed_intent exists and only on the SQL
                                    path.
  route_by_classification        -> parses query_classification's reasoned
                                    JSON output and emits "SQL" | "VECTOR".
  check_fallback                   -> post-synthesis safety valve, shared by
                                    BOTH branches.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from google.adk import Context, Event
from google.adk.workflow import DEFAULT_ROUTE, node

from tools.schema_tool import fetch_schema_overview, fetch_schema_relevant_detail

logger = logging.getLogger("adk_rag.services.graph_nodes")


def _extract_json_payload(raw: Any) -> dict[str, Any]:
    """
    Defensively extracts a JSON object from string, dict, or LLM markdown output.
    Handles extra commentary, markdown blocks (```json ... ```), and trailing noise.
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}

    cleaned = raw.strip()

    # 1. Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # 2. Try standard json.loads
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # 3. Extract the first {...} blob via regex if the LLM included surrounding text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return {}


@node
async def load_schema_context(ctx: Context) -> None:
    """Grounds the whole run in a cheap schema overview before any LLM agent runs."""
    ctx.state["db_schema_summary"] = await fetch_schema_overview()


@node
async def load_relevant_schema_detail(ctx: Context) -> None:
    """
    SQL-branch only. Fetches full column metadata filtered to the entities/
    metrics/aliases query_understanding already extracted, so
    query_generation_agent gets exactly the detail it needs and no more.
    """
    raw_intent = ctx.state.get("parsed_intent", "{}")
    intent = _extract_json_payload(raw_intent)

    ctx.state["db_schema_detail"] = await fetch_schema_relevant_detail(
        entities=intent.get("core_entities", []) or [],
        metrics=intent.get("metrics", []) or [],
        aliases=intent.get("aliases", {}) or {},
    )


@node
async def route_by_classification(ctx: Context) -> Event:
    """
    Parses state['query_path'] safely and returns an Event with route="SQL" or "VECTOR".
    Includes multiple fallback layers if the LLM hallucinated the output format.
    """
    raw = ctx.state.get("query_path", "")
    path: str | None = None

    # Try parsing via helper
    parsed = _extract_json_payload(raw)
    if "path" in parsed and isinstance(parsed["path"], str):
        path = parsed["path"]

    # Fallback: Check if "SQL" or "VECTOR" exists as a plain string inside the output
    if not path and isinstance(raw, str):
        upper_raw = raw.upper()
        if "SQL" in upper_raw:
            path = "SQL"
        elif "VECTOR" in upper_raw:
            path = "VECTOR"

    # Default fallback to VECTOR if parsing completely fails
    if not path:
        logger.warning(
            "route_by_classification: could not parse route from query_path (%r). Defaulting to VECTOR.",
            raw,
        )
        path = "VECTOR"

    path = path.strip().upper()
    logger.info("route_by_classification: selecting route %s", path)

    return Event(route=path)


@node
async def check_fallback(ctx: Context) -> str:
    """
    Post-synthesis safety valve shared by both branches. Sends the run to
    external_support if execution/retrieval failed or synthesis couldn't
    safely answer, otherwise lets the branch terminate normally (final_answer
    is already populated).
    """
    final_answer = str(ctx.state.get("final_answer", "")).strip()
    execution_result = str(ctx.state.get("execution_result", ""))
    retrieval_result = str(ctx.state.get("vector_retrieval_result", ""))

    needs_support = (
        final_answer == "ROUTE_TO_SUPPORT"
        or "EXECUTION_ERROR" in execution_result
        or "RETRIEVAL_ERROR" in retrieval_result
        or not final_answer
    )
    if needs_support:
        logger.info("check_fallback: routing to external_support")
        return "NEEDS_SUPPORT"
    return DEFAULT_ROUTE