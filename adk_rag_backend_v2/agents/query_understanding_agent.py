"""
agents/query_understanding_agent.py
--------------------------------------
Agent 1 of 10. The pipeline's "working memory" -- extracts semantic intent,
decomposes multi-hop questions, and flags ambiguity BEFORE anything
downstream tries to answer in one shot. Writes `ctx.state["parsed_intent"]`
(see schemas/state_schemas.py::ParsedIntent).

Context-window note: `include_contents="none"` -- this agent relies solely on
its own instruction (with `{db_schema_summary}` substituted by the ADK
runtime from state) plus the user's actual question, not on any inherited
conversation history. `{db_schema_summary}` is the CHEAP overview from
`tools.schema_tool.fetch_schema_overview` (table/column NAMES + one-line
summaries) -- enough to map user language to real fields without paying for
full per-column descriptions this early.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-2.5-flash")

query_understanding_agent = Agent(
    name="query_understanding",
    model=_MODEL,
    description="Extracts semantic intent, decomposes multi-hop questions, and flags ambiguity before any query is generated.",
    include_contents="none",
    instruction=(
        "You are the reasoning entry point of an analytics assistant that works over "
        "WHATEVER dataset has actually been ingested -- never assume a business domain; "
        "ground yourself only in the schema below and the question itself.\n\n"
        "INGESTED SCHEMA:\n{db_schema_summary}\n\n"
        "Read the user's question and think like an analyst doing a deep dive:\n"
        "1. Identify core entities, metrics, filters, and aliases -- map the user's "
        "   words to real table/column names above wherever plausible.\n"
        "2. If the question genuinely requires multiple logical steps (e.g. 'which "
        "   region grew fastest and what drove it'), decompose it into an ordered "
        "   sub_questions list. Leave it empty for single-hop questions.\n"
        "3. If the question references something that doesn't clearly map to anything "
        "   in the schema above, set ambiguous=true and write one concrete "
        "   clarification_question. Do not flag ambiguity just because the question is "
        "   broad -- only when a wrong guess would be expensive.\n"
        "4. Record a one-sentence reasoning_notes explaining your interpretation (shown "
        "   to developers, not the end user -- be terse).\n\n"
        "Emit ONLY a compact JSON object (no prose, no markdown fences):\n"
        '{"raw_query": str, "core_entities": [str], "metrics": [str], "filters": {}, '
        '"aliases": {}, "is_time_series": bool, '
        '"time_grain": "day"|"week"|"month"|"quarter"|"year"|null, '
        '"comparison_requested": bool, "sub_questions": [str], "ambiguous": bool, '
        '"clarification_question": str|null, "reasoning_notes": str}\n'
        "Set comparison_requested=true only for explicit MoM/YoY/period-over-period asks. "
        "Never invent entities that aren't implied by the question or present in the schema."
    ),
    output_key="parsed_intent",
)
