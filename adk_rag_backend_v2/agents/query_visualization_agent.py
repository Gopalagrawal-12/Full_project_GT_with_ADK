"""
agents/query_visualization_agent.py
---------------------------------------
Agent 7 of 10. Converts the raw database result array from execution_result
into a natural-language answer. Writes `ctx.state["final_answer"]`.

Blind-trusts pre-filtered results, maps empty result sets to a clear
structural statement instead of breaking, and signals failures upstream by
emitting the literal string "ROUTE_TO_SUPPORT" -- `check_fallback` in
services/graph_nodes.py watches for exactly that string to branch into
`external_support`. Needs only the execution result and the original
question -- not the schema, not the SQL.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-flash-latest")

query_visualization_agent = Agent(
    name="query_visualization",
    model=_MODEL,
    description="Converts raw DB result arrays into a natural-language answer.",
    include_contents="none",
    instruction=(
        "ORIGINAL QUESTION CONTEXT:\n{parsed_intent}\n\n"
        "EXECUTION RESULT (JSON from execute_sql):\n{execution_result}\n\n"
        "Rules:\n"
        "- Blind-trust the rows you are given -- they are already filtered/aggregated. "
        "  Do not re-derive or second-guess numbers.\n"
        "- If execution_result indicates success=false or starts with "
        "  'EXECUTION_ERROR:', do NOT attempt to answer -- output exactly: "
        "  ROUTE_TO_SUPPORT\n"
        "- If rows is an empty list, respond with a clear structural statement such as "
        "  'No records matched that filter for the selected period.' -- never fabricate "
        "  data.\n"
        "- Otherwise, produce a concise, natural-language answer citing the concrete "
        "  numbers/rows returned, addressing raw_query from the context above. No SQL, "
        "  no JSON, no markdown tables unless the user explicitly asked for a table."
    ),
    output_key="final_answer",
)
