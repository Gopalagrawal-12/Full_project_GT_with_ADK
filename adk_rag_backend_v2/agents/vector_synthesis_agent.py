"""
agents/vector_synthesis_agent.py
-------------------------------------
Agent 9 of 10. VECTOR-branch counterpart to `query_visualization_agent`.
Turns `vector_retrieval_result` (a ranked list of chunks) into a grounded,
cited natural-language answer. Writes `ctx.state["final_answer"]`.

"Smart" behavior: deliberately NOT "summarize whatever came back." Reasons
across chunks like an analyst doing a literature review -- reconciles
agreement/disagreement between sources, notices gaps, and says so -- rather
than flattening everything into one confident paragraph. Needs only the
retrieval result and the original question.
"""

from __future__ import annotations

import os

from google.adk import Agent

_MODEL = os.getenv("ADK_AGENT_MODEL", "gemini-2.5-flash")

vector_synthesis_agent = Agent(
    name="vector_synthesis",
    model=_MODEL,
    description="Synthesizes retrieved document chunks into a grounded, cited answer.",
    include_contents="none",
    instruction=(
        "ORIGINAL QUESTION CONTEXT:\n{parsed_intent}\n\n"
        "RETRIEVED CHUNKS (JSON from vector_search):\n{vector_retrieval_result}\n\n"
        "Rules:\n"
        "- If the retrieval result indicates success=false or starts with "
        "  'RETRIEVAL_ERROR:', do NOT attempt to answer -- output exactly: "
        "  ROUTE_TO_SUPPORT\n"
        "- If results is an empty list, respond with a clear structural statement such "
        "  as 'No ingested documents matched that question.' -- never fabricate "
        "  content.\n"
        "- Otherwise, read across ALL returned chunks like an analyst doing a source "
        "  review, not a single-passage summarizer:\n"
        "    * Synthesize the answer from the chunks that actually support it -- ignore "
        "      chunks with low similarity that don't address the question.\n"
        "    * If sources agree, state the answer plainly. If sources conflict or only "
        "      partially cover the question, say so explicitly rather than picking one "
        "      silently.\n"
        "    * Cite each claim's origin inline as (source: <title>) so the user can "
        "      trace it back -- never assert something no retrieved chunk supports.\n"
        "    * If the retrieved chunks only partially answer raw_query, answer what "
        "      they support and explicitly name what's missing, rather than padding "
        "      the gap with your own general knowledge.\n"
        "- Keep the answer concise and in plain language -- no raw JSON, no chunk dumps."
    ),
    output_key="final_answer",
)
