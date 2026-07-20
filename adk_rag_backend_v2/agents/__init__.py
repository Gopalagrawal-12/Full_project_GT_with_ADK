"""
agents package
----------------
Each of the 10 micro-agents lives in its own module, one responsibility per
file. This package re-exports all of them so services/orchestrator.py can do:

    from agents import query_understanding_agent, vector_retrieval_agent, ...

State handoff map (who writes what key in ctx.state)
------------------------------------------------------
  SQL branch:
    query_understanding_agent    -> "parsed_intent"
    query_classification_agent   -> "query_path"
    time_lag_agent                 -> "time_series_hint"
    query_generation_agent         -> "generated_sql"
    query_review_agent              -> "reviewed_sql"
    query_execution_agent            -> "execution_result"
    query_visualization_agent         -> "final_answer"

  VECTOR branch:
    vector_retrieval_agent       -> "vector_retrieval_result"
    vector_synthesis_agent        -> "final_answer"

  Fallback (either branch):
    external_support_agent       -> "final_answer"
"""

from agents.external_support_agent import external_support_agent
from agents.query_classification_agent import query_classification_agent
from agents.query_execution_agent import query_execution_agent
from agents.query_generation_agent import query_generation_agent
from agents.query_review_agent import query_review_agent
from agents.query_understanding_agent import query_understanding_agent
from agents.query_visualization_agent import query_visualization_agent
from agents.time_lag_agent import time_lag_agent
from agents.vector_retrieval_agent import vector_retrieval_agent
from agents.vector_synthesis_agent import vector_synthesis_agent

__all__ = [
    "query_understanding_agent",
    "query_classification_agent",
    "time_lag_agent",
    "query_generation_agent",
    "query_review_agent",
    "query_execution_agent",
    "query_visualization_agent",
    "vector_retrieval_agent",
    "vector_synthesis_agent",
    "external_support_agent",
]
