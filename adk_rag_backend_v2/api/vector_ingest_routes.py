"""
api/vector_ingest_routes.py
--------------------------------
POST /ingest/documents         -> kicks off a background chunk+embed+store job, returns job_id
GET  /ingest/documents/status   -> polling endpoint for that job's progress

Mirrors api/ingest_routes.py's job-tracking pattern (separate in-memory dict,
separate job-id namespace) since tabular and document ingestion are distinct
concerns that happen to share the same status-polling shape
(IngestionStatusResponse).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from schemas.ingestion_schemas import IngestionStage, IngestionStatusResponse
from services.vector_ingestion_service import VectorIngestionPipeline

logger = logging.getLogger("adk_rag.api.vector_ingest_routes")
router = APIRouter()

_document_jobs: dict[str, IngestionStatusResponse] = {}

# One pipeline instance (and its chunker/embedder) reused across requests --
# construction loads the tokenizer/model, so it shouldn't happen per-request.
_pipeline: VectorIngestionPipeline | None = None


def _get_pipeline() -> VectorIngestionPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = VectorIngestionPipeline()
    return _pipeline


async def _run_document_ingestion(
    job_id: str, file_bytes: bytes, file_name: str, dataset_label: str | None
) -> None:
    job = _document_jobs[job_id]
    job.status = IngestionStage.PROCESSING
    job.started_at = datetime.now(timezone.utc)

    def progress_cb(step: str, pct: float) -> None:
        job.current_step = step
        job.progress_pct = pct

    try:
        pipeline = _get_pipeline()
        result = await pipeline.ingest_bytes(
            file_name=file_name, file_bytes=file_bytes, dataset_label=dataset_label, progress_cb=progress_cb
        )
        job.rows_ingested = result["chunks_created"]
        job.progress_pct = 100.0
        job.current_step = "done"
        job.status = IngestionStage.COMPLETED
    except Exception as exc:  # noqa: BLE001 - background task must never crash silently
        logger.exception("Document ingestion job %s failed", job_id)
        job.status = IngestionStage.FAILED
        job.error = str(exc)
    finally:
        job.finished_at = datetime.now(timezone.utc)


@router.post("/ingest/documents", response_model=IngestionStatusResponse)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    dataset_label: str | None = None,
) -> IngestionStatusResponse:
    file_bytes = await file.read()
    job = IngestionStatusResponse.new(file_name=file.filename or "upload")
    _document_jobs[job.job_id] = job

    background_tasks.add_task(_run_document_ingestion, job.job_id, file_bytes, job.file_name, dataset_label)
    return job


@router.get("/ingest/documents/status", response_model=IngestionStatusResponse)
async def ingest_document_status(job_id: str) -> IngestionStatusResponse:
    job = _document_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No document ingestion job with id {job_id}")
    return job
