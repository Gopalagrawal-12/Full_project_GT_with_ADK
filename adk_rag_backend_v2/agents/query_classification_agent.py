"""
agents/query_classification_agent.py
----------------------------------------
Agent 2 of 10. Decides SQL vs VECTOR using the CHEAP schema overview only --
it needs to know WHAT exists (tables vs documents), not full per-column
detail, to make this call. Writes `ctx.state["query_path"]` as JSON matching
schemas.state_schemas.QueryClassification, which `route_by_classification` in
services/graph_nodes.py parses to steer the branch.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-flash-latest")

query_classification_agent = Agent(
    name="query_classification",
    model=_MODEL,
    description="Decides SQL vs VECTOR execution path with an explicit, reasoned confidence score.",
    include_contents="none",
    instruction=(
        "PARSED INTENT:\n{parsed_intent}\n\n"
        "INGESTED SCHEMA:\n{db_schema_summary}\n\n"
        "Decide the execution path:\n"
        "  SQL    -> the question maps to aggregations/filters/joins/rankings over "
        "            structured tabular fields listed above.\n"
        "  VECTOR -> the question is open-ended, asks about unstructured document "
        "            content, wants explanations/context/'why', or references concepts "
        "            that read like prose rather than tabular fields.\n\n"
        "A question can look like both -- e.g. 'why did revenue drop in March' has a "
        "tabular component (revenue, March) and a narrative component (why). Prefer "
        "whichever path answers the PRIMARY ask; note the tension in `reason`. Default "
        "to SQL only when entities/metrics clearly reference tabular fields above -- do "
        "not default to SQL out of habit for genuinely narrative questions.\n\n"
        "Emit ONLY a compact JSON object (no prose, no markdown fences):\n"
        '{"path": "SQL"|"VECTOR", "confidence": float between 0 and 1, "reason": str}\n'
        "Keep `reason` to one sentence."
    ),
    output_key="query_path",
)
