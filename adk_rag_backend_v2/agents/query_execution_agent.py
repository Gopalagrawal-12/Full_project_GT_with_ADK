"""
agents/query_execution_agent.py
------------------------------------
Agent 6 of 10. Binds the `execute_sql` tool and runs `reviewed_sql` against
Postgres. Writes `ctx.state["execution_result"]` with the tool's raw JSON
output (see tools/sql_execution_tool.py). Needs only the reviewed SQL itself.
"""

from __future__ import annotations

import os

from google.adk import Agent
from google.adk.tools import FunctionTool

from tools.sql_execution_tool import execute_sql

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-flash-latest")

query_execution_agent = Agent(
    name="query_execution",
    model=_MODEL,
    description="Executes the reviewed SQL against Postgres via the execute_sql tool.",
    include_contents="none",
    instruction=(
        "REVIEWED SQL TO EXECUTE:\n{reviewed_sql}\n\n"
        "Call the `execute_sql` tool with the exact string above as the `query` "
        "argument. Do not modify it. Return the tool's raw JSON output verbatim -- do "
        "not summarize or reformat it."
    ),
    tools=[FunctionTool(execute_sql)],
    output_key="execution_result",
)
