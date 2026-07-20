"""
schemas package
-----------------
Re-exports every contract so callers can do `from schemas import ChatRequest`
instead of reaching into the individual submodules.
"""

from schemas.chat_schemas import ChatRequest, ChatResponse
from schemas.ingestion_schemas import (
    IngestionStage,
    IngestionStatusResponse,
    IngestRequest,
)
from schemas.state_schemas import (
    FinalAnswer,
    GeneratedSQL,
    ParsedIntent,
    QueryClassification,
    RetrievedChunk,
    SQLExecutionResult,
    VectorRetrievalResult,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "IngestionStage",
    "IngestionStatusResponse",
    "IngestRequest",
    "ParsedIntent",
    "QueryClassification",
    "GeneratedSQL",
    "SQLExecutionResult",
    "FinalAnswer",
    "RetrievedChunk",
    "VectorRetrievalResult",
]
