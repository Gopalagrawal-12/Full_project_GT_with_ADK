"""
schemas/chat_schemas.py
------------------------
Request/response contracts for the POST /chat endpoint.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Inbound payload for POST /chat."""

    message: str = Field(..., min_length=1, description="Raw user question.")
    session_id: Optional[str] = Field(
        default=None,
        description="Existing ADK session id. A new one is minted if omitted.",
    )
    user_id: str = Field(
        default="anonymous",
        description="Caller identity, used for session partitioning.",
    )


class ChatResponse(BaseModel):
    """Outbound payload for POST /chat."""

    session_id: str
    answer: str
    query_path: Optional[Literal["SQL", "VECTOR"]] = None
    sql_executed: Optional[str] = None
    row_count: Optional[int] = None
    elapsed_ms: Optional[float] = None
