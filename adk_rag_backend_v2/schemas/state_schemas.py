"""
schemas/state_schemas.py
--------------------------
The inter-agent state contract. These models describe the shape of every
value written into `ctx.state` as it moves through the workflow graph. Each
agent should validate its own state slice into one of these on the way in
and out, even though the ADK runtime itself passes plain JSON/dict values.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ParsedIntent(BaseModel):
    """Output of `query_understanding`, read from `ctx.state["parsed_intent"]`."""

    raw_query: str
    core_entities: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    aliases: dict[str, str] = Field(default_factory=dict)
    is_time_series: bool = False
    time_grain: Optional[Literal["day", "week", "month", "quarter", "year"]] = None
    comparison_requested: bool = False  # e.g. MoM / YoY growth
    sub_questions: list[str] = Field(
        default_factory=list,
        description="Decomposition of multi-hop questions into ordered, answerable sub-questions.",
    )
    ambiguous: bool = False
    clarification_question: Optional[str] = None
    reasoning_notes: str = Field(
        default="",
        description="Short trace of how intent was derived — surfaced to the UI, not the end user.",
    )


class QueryClassification(BaseModel):
    """Output of `query_classification`."""

    path: Literal["SQL", "VECTOR"]
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str = ""


class GeneratedSQL(BaseModel):
    """Output of `query_generation` (and re-emitted by `query_review`)."""

    sql: str
    notes: str = ""
    reviewed: bool = False


class SQLExecutionResult(BaseModel):
    """Output of `query_execution`. Always populated, even on failure."""

    success: bool
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    error: Optional[str] = None
    elapsed_ms: float = 0.0


class FinalAnswer(BaseModel):
    """Terminal payload produced by `query_visualization` or `external_support`."""

    answer: str
    used_fallback: bool = False


class RetrievedChunk(BaseModel):
    """One row of `vector_search`'s output, as consumed by `vector_synthesis_agent`."""

    content: str
    title: str
    source: str
    chunk_index: int
    similarity: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorRetrievalResult(BaseModel):
    """Output of `vector_retrieval_agent` (mirrors SQLExecutionResult for the VECTOR branch)."""

    success: bool
    results: list[RetrievedChunk] = Field(default_factory=list)
    result_count: int = 0
    error: Optional[str] = None
    elapsed_ms: float = 0.0
