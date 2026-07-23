"""
agents/external_support_agent.py
-------------------------------------
Agent 10 of 10. Shared fallback handler invoked when: the classifier routed
to VECTOR with no matching documents, execute_sql returned an
EXECUTION_ERROR, vector_search returned a RETRIEVAL_ERROR, or synthesis
emitted ROUTE_TO_SUPPORT. Writes `ctx.state["final_answer"]` just like
`query_visualization`/`vector_synthesis` do, so the API layer never needs to
know which branch produced the answer.

Uses optional (`?`) placeholders since only a subset of these state keys
will actually be populated depending on which branch failed -- ADK
substitutes missing optional keys with an empty string instead of raising.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-2.5-flash")

external_support_agent = Agent(
    name="external_support",
    model=_MODEL,
    description="Fallback agent for connection loss, empty targets, or unroutable queries.",
    include_contents="none",
    instruction=(
        "You are the fallback handler for a pipeline that just failed to produce a safe "
        "answer. Whatever context below is present tells you what happened; some fields "
        "may be blank depending on where the failure occurred.\n\n"
        "PARSED INTENT (may be blank): {parsed_intent?}\n"
        "SQL EXECUTION RESULT (may be blank): {execution_result?}\n"
        "VECTOR RETRIEVAL RESULT (may be blank): {vector_retrieval_result?}\n\n"
        "Apologize briefly, explain in plain language (never expose raw SQL/error text "
        "or stack traces to the end user), and suggest one concrete next step -- e.g. "
        "rephrasing the question, checking that the relevant dataset has been ingested, "
        "or narrowing the date range. Keep it to 2-3 sentences."
    ),
    output_key="final_answer",
)
