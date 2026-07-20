"""
schemas/ingestion_schemas.py
------------------------------
Contracts for POST /ingest and GET /ingest/status. Backed by an in-memory
dict that the background worker mutates as it steps through parsing ->
validation -> row insertion, so the frontend can poll for a progress bar.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IngestionStage(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionStatusResponse(BaseModel):
    """Shape returned by GET /ingest/status."""

    job_id: str
    status: IngestionStage = IngestionStage.IDLE
    current_step: str = "waiting"
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    file_name: Optional[str] = None
    rows_ingested: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @staticmethod
    def new(file_name: str) -> "IngestionStatusResponse":
        return IngestionStatusResponse(
            job_id=str(uuid.uuid4()),
            status=IngestionStage.IDLE,
            current_step="queued",
            file_name=file_name,
        )


class IngestRequest(BaseModel):
    """Metadata accompanying an ingestion trigger (multipart file is separate)."""

    file_name: str
    dataset_label: Optional[str] = None
