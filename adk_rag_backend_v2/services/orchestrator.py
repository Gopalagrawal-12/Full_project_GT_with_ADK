"""
services/orchestrator.py
--------------------------
Builds the ADK `Workflow` graph: a directed pipeline from START through the
10 micro-agents in agents/, with a conditional branch after classification
(SQL vs VECTOR) and a shared fallback branch into `external_support` whenever
either branch fails or can't produce a safe answer.

Graph shape
-----------
    START
      -> load_schema_context   (cheap grounding: table/doc names, one-line summaries)
      -> query_understanding
      -> query_classification
      -> route_by_classification (function node, emits route "SQL" | "VECTOR")
           "SQL"    -> time_lag -> load_relevant_schema_detail (entity-filtered,
                       full column metadata -- SQL-branch only, computed only
                       after parsed_intent exists) -> query_generation
                       -> query_review -> query_execution -> query_visualization
                       -> check_fallback
           "VECTOR" -> vector_retrieval -> vector_synthesis -> check_fallback
                            check_fallback:
                              "NEEDS_SUPPORT" -> external_support   (terminal)
                              <no match / DEFAULT> -> (terminal, final_answer already set)

Only three nodes ever write `state["final_answer"]`: `query_visualization`,
`vector_synthesis`, and `external_support`. The API layer only ever needs to
read that one key, regardless of which branch executed.

Context-window discipline: `load_schema_context` fetches a cheap overview
used by every agent that needs SOME schema awareness (understanding,
classification). The expensive, fully-detailed column metadata is fetched
only once we know we're on the SQL path AND only after `parsed_intent` tells
us which entities/metrics actually matter -- see
`services/graph_nodes.py::load_relevant_schema_detail` and
`tools/schema_tool.py::fetch_schema_relevant_detail`.
"""

from __future__ import annotations

from google.adk.workflow import START, Workflow

from agents import (
    external_support_agent,
    query_classification_agent,
    query_execution_agent,
    query_generation_agent,
    query_review_agent,
    query_understanding_agent,
    query_visualization_agent,
    time_lag_agent,
    vector_retrieval_agent,
    vector_synthesis_agent,
)
from services.graph_nodes import (
    check_fallback,
    load_relevant_schema_detail,
    load_schema_context,
    route_by_classification,
)


def build_sql_rag_workflow() -> Workflow:
    """Constructs the graph-based Workflow. Call once at app startup and reuse."""
    return Workflow(
        name="sql_rag_pipeline",
        edges=[
            (
                START,
                load_schema_context,
                query_understanding_agent,
                query_classification_agent,
                route_by_classification,
            ),
            (
                route_by_classification,
                {
                    "SQL": (time_lag_agent,),
                    "VECTOR": (vector_retrieval_agent,),
                },
            ),
            # SQL branch
            (
                time_lag_agent,
                load_relevant_schema_detail,
                query_generation_agent,
                query_review_agent,
                query_execution_agent,
                query_visualization_agent,
                check_fallback,
            ),
            # VECTOR branch -- converges on the same check_fallback node as SQL
            (
                vector_retrieval_agent,
                vector_synthesis_agent,
                check_fallback,
            ),
            (
                check_fallback,
                {"NEEDS_SUPPORT": (external_support_agent,)},
            ),
        ],
    )


# Module-level singleton -- the graph definition is stateless and safe to reuse
# across requests; per-request state lives in the ADK Session, not the graph.
sql_rag_workflow = build_sql_rag_workflow()
