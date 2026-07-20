"""
agents/vector_retrieval_agent.py
-------------------------------------
Agent 8 of 10. VECTOR-branch counterpart to `query_execution_agent`. Binds
the `vector_search` tool and retrieves the chunks most relevant to the
question. Writes `ctx.state["vector_retrieval_result"]` with the tool's raw
JSON output (see tools/vector_search_tool.py). Needs only `parsed_intent`.

"Smart" behavior: rather than blindly forwarding the raw user question, this
agent first reformulates it into a dense, keyword-rich retrieval query --
resolving pronouns, expanding abbreviations, and folding in the entities
`query_understanding` already extracted -- since embedding similarity is far
more sensitive to phrasing than an LLM's own language understanding is.
"""

from __future__ import annotations

import os

from google.adk import Agent
from google.adk.tools import FunctionTool

from tools.vector_search_tool import vector_search

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-flash-latest")

vector_retrieval_agent = Agent(
    name="vector_retrieval",
    model=_MODEL,
    description="Reformulates the question for retrieval and runs a vector similarity search over ingested documents.",
    include_contents="none",
    instruction=(
        "PARSED INTENT:\n{parsed_intent}\n\n"
        "Steps:\n"
        "1. Silently reformulate raw_query into a dense retrieval query: resolve "
        "   pronouns, expand abbreviations, and include the core_entities/metrics above "
        "   -- this query is NOT shown to the user, it only improves embedding recall.\n"
        "2. Call the `vector_search` tool with that reformulated query as `query`. Use "
        "   `top_k=5` unless the question implies it needs broader coverage (e.g. "
        "   'summarize everything about X'), in which case use `top_k=10`.\n"
        "3. Return the tool's raw JSON output verbatim -- do not summarize, filter, or "
        "   reformat it. Downstream synthesis handles interpretation."
    ),
    tools=[FunctionTool(vector_search)],
    output_key="vector_retrieval_result",
)
