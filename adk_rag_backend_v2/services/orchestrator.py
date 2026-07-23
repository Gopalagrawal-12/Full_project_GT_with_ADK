"""
services/orchestrator.py
--------------------------
Builds the ADK `Workflow` graph with throttling delays and isolated branch nodes.
"""

from __future__ import annotations

import asyncio
import logging
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

logger = logging.getLogger("adk_rag.orchestrator")

# ---------------------------------------------------------
# THROTTLING NODES (Free Tier Workaround)
# Every delay node MUST be a unique function reference so
# branch paths do not accidentally cross-trigger each other.
# ---------------------------------------------------------
async def delay_1(ctx):
    logger.info("Throttling pipeline (Delay 1/5) for 15s to respect Gemini Free Tier limits...")
    await asyncio.sleep(15)
    return {}

async def delay_2(ctx):
    logger.info("Throttling pipeline (Delay 2/5 - SQL) for 15s to respect Gemini Free Tier limits...")
    await asyncio.sleep(15)
    return {}

async def delay_3(ctx):
    logger.info("Throttling pipeline (Delay 3/5 - SQL) for 15s to respect Gemini Free Tier limits...")
    await asyncio.sleep(15)
    return {}

async def delay_4(ctx):
    logger.info("Throttling pipeline (Delay 4/5 - SQL) for 15s to respect Gemini Free Tier limits...")
    await asyncio.sleep(15)
    return {}

async def delay_5(ctx):
    logger.info("Throttling pipeline (Delay 5/5 - SQL) for 15s to respect Gemini Free Tier limits...")
    await asyncio.sleep(15)
    return {}

# Dedicated delay function for the VECTOR path
async def vector_delay_1(ctx):
    logger.info("Throttling pipeline (Delay - Vector Branch) for 15s to respect Gemini Free Tier limits...")
    await asyncio.sleep(15)
    return {}
# ---------------------------------------------------------

def build_sql_rag_workflow() -> Workflow:
    """Constructs the graph-based Workflow."""
    return Workflow(
        name="sql_rag_pipeline",
        edges=[
            (
                START,
                load_schema_context,
                query_understanding_agent,
                delay_1,                     # Pause before classification
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
                delay_2,                     # Pause before generation
                query_generation_agent,
                delay_3,                     # Pause before review
                query_review_agent,
                delay_4,                     # Pause before execution
                query_execution_agent,
                delay_5,                     # Pause before visualization
                query_visualization_agent,
                check_fallback,
            ),
            # VECTOR branch -- strictly isolated using vector_delay_1
            (
                vector_retrieval_agent,
                vector_delay_1,              # Dedicated vector delay
                vector_synthesis_agent,
                check_fallback,
            ),
            (
                check_fallback,
                {"NEEDS_SUPPORT": (external_support_agent,)},
            ),
        ],
    )

sql_rag_workflow = build_sql_rag_workflow()