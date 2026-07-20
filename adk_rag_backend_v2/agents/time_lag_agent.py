"""
agents/time_lag_agent.py
---------------------------
Agent 3 of 10. Injects CTE structural guidance when time-series growth
analysis (MoM/YoY) is flagged in parsed_intent. Writes
`ctx.state["time_series_hint"]`, which `query_generation_agent` folds into
the SQL it produces. Needs only `parsed_intent` -- no schema access at all.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-flash-latest")

time_lag_agent = Agent(
    name="time_lag",
    model=_MODEL,
    description="Injects CTE structural guidance when time-series growth analysis (MoM/YoY) is requested.",
    include_contents="none",
    instruction=(
        "PARSED INTENT:\n{parsed_intent}\n\n"
        "If is_time_series is false, output exactly: NONE\n"
        "Otherwise output short structural guidance (not full SQL) describing the CTE "
        "shape query_generation should use, e.g.: 'Use a CTE `periods` bucketing the "
        "date column by DATE_TRUNC(month, ...), then a second CTE with LAG() OVER "
        "(ORDER BY period) to compute period-over-period deltas.' Keep it to 2-3 "
        "sentences -- query_generation will finalize the actual SQL."
    ),
    output_key="time_series_hint",
)
