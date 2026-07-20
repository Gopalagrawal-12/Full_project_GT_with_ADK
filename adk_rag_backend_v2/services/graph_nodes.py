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

from google.adk import Context, Event
from google.adk.workflow import DEFAULT_ROUTE, node

from tools.schema_tool import fetch_schema_overview, fetch_schema_relevant_detail

logger = logging.getLogger("adk_rag.services.graph_nodes")


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
    try:
        intent = json.loads(raw_intent) if isinstance(raw_intent, str) else (raw_intent or {})
    except (json.JSONDecodeError, TypeError):
        intent = {}

    ctx.state["db_schema_detail"] = await fetch_schema_relevant_detail(
        entities=intent.get("core_entities", []) or [],
        metrics=intent.get("metrics", []) or [],
        aliases=intent.get("aliases", {}) or {},
    )

@node
async def route_by_classification(ctx: Context):
    raw = ctx.state["query_path"]

    if isinstance(raw, str):
        import json
        raw = json.loads(raw)

    path = raw["path"].upper()

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
