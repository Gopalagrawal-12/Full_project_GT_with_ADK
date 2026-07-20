
"""
api/ingest_routes.py
------------------------
POST /ingest         -> kicks off a background ingestion job, returns job_id immediately
GET  /ingest/status   -> polling endpoint the frontend hits for a progress bar

Ingestion status is tracked in an in-memory dict (`_ingestion_jobs`). Fine for
a single-instance deployment; swap for Redis/DB-backed tracking behind a load
balancer.

Column metadata is NEVER supplied by the caller. `_run_ingestion` always
derives it itself, via `generate_column_metadata`, by showing an LLM (Groq)
a small sample of the actual parsed data and asking it to describe the table
and each column -- semantics, synonyms, and SQL-generation hints -- which is
exactly what `query_generation_agent` needs to write correct SQL against a
dataset it's never seen before. This is what makes the backend usable for
*any* CSV or Excel file without a human pre-annotating a schema.
"""

from __future__ import annotations

import io
import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from schemas.ingestion_schemas import IngestionStage, IngestionStatusResponse
from utils.db_pool import get_pool
from utils.providers import get_groq_client, get_metadata_model
import dotenv
dotenv.load_dotenv()
logger = logging.getLogger("adk_rag.api.ingest_routes")
router = APIRouter()

_ingestion_jobs: dict[str, IngestionStatusResponse] = {}


def _fallback_metadata(df: pd.DataFrame) -> dict[str, Any]:
    """
    Used only if the LLM call fails or returns something unparseable, so
    ingestion never hard-fails just because metadata generation had a bad
    day -- the pipeline degrades to bare column names instead of blocking.
    """
    return {
        "table_summary": "Auto-generated metadata unavailable; column semantics unknown.",
        "columns": {
            col: {"description": "", "synonyms": [], "sql_hints": f"pandas dtype: {dtype}"}
            for col, dtype in df.dtypes.astype(str).items()
        },
    }


async def generate_column_metadata(df: pd.DataFrame) -> dict[str, Any]:
    """
    Uses an LLM (Groq) to summarize what the table and each column mean,
    grounded in a real sample of the parsed data -- not just column names.
    Never raises: falls back to `_fallback_metadata` on any failure (network,
    rate limit, malformed JSON) so ingestion can still proceed.
    """
    try:
        sample_df = df.head(5).where(pd.notnull(df.head(5)), None)
        sample_data = json.loads(sample_df.to_json(orient="records", date_format="iso"))

        client = get_groq_client()
        prompt = f"""
You are an expert Data Architect. Analyze this dataframe sample and generate a rich metadata dictionary to help a Text-to-SQL LLM understand and query this data.

Sample Data: {json.dumps(sample_data)}

Return ONLY a JSON object matching this EXACT schema:
{{
    "table_summary": "A 1-2 sentence overview of what this entire dataset represents.",
    "columns": {{
        "Exact_Column_Name_Here": {{
            "description": "Clear semantic description of what the data represents.",
            "synonyms": ["list", "of", "alternative", "search", "terms", "or", "jargon"],
            "sql_hints": "Specific SQL casting, math, or formatting rules (e.g., 'Cast to numeric for SUM', 'Date format is YYYY-MM-DD', 'Filter using ILIKE')"
        }}
    }}
}}
"""
        response = await client.chat.completions.create(
            model=get_metadata_model(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        metadata = json.loads(response.choices[0].message.content)

        if not isinstance(metadata, dict) or "columns" not in metadata:
            raise ValueError("LLM metadata response missing required 'columns' key.")

        # Backfill any column the LLM skipped so every real column is still described.
        for col in df.columns:
            metadata["columns"].setdefault(
                col, {"description": "", "synonyms": [], "sql_hints": ""}
            )
        return metadata

    except Exception:  # noqa: BLE001 - metadata generation must never block ingestion
        logger.exception("generate_column_metadata failed; falling back to bare column names")
        return _fallback_metadata(df)


def _dataframe_to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """NaN/NaT -> None, everything else JSON-serializable, one dict per row."""
    clean = df.where(pd.notnull(df), None)
    return json.loads(clean.to_json(orient="records", date_format="iso"))


async def _run_ingestion(
    job_id: str, file_bytes: bytes, file_name: str, dataset_label: str | None
) -> None:
    """
    Background worker: parses the uploaded file (CSV or Excel), auto-generates column
    metadata via Groq, and loads it row-by-row into `data_rows`, mutating the
    shared in-memory status payload as it steps through each stage so
    /ingest/status has something fresh to report.
    """
    job = _ingestion_jobs[job_id]
    job.status = IngestionStage.PROCESSING
    job.started_at = datetime.now(timezone.utc)

    try:
        job.current_step = "parsing_file"
        job.progress_pct = 10.0
        try:
            file_extension = pathlib.Path(file_name).suffix.lower()
            if file_extension == '.csv':
                df = pd.read_csv(io.BytesIO(file_bytes))
            elif file_extension in ['.xlsx', '.xls']:
                df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl')
            else:
                raise ValueError(f"Unsupported file format: {file_extension}. Please upload a CSV or Excel file.")
        except Exception as exc:
            raise ValueError(f"Could not parse '{file_name}': {exc}") from exc

        job.current_step = "validating_rows"
        job.progress_pct = 25.0
        if df.empty:
            raise ValueError("No rows parsed from uploaded file.")

        job.current_step = "generating_column_metadata"
        job.progress_pct = 40.0
        metadata = await generate_column_metadata(df)

        rows = _dataframe_to_json_records(df)

        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                job.current_step = "inserting_file_metadata"
                job.progress_pct = 60.0
                file_row_id = await conn.fetchval(
                    """
                    INSERT INTO file_metadata (file_name, dataset_label, columns, row_count)
                    VALUES ($1, $2, $3::jsonb, $4)
                    RETURNING id
                    """,
                    file_name, dataset_label, json.dumps(metadata), len(rows),
                )

                job.current_step = "inserting_data_rows"
                job.progress_pct = 80.0
                await conn.executemany(
                    "INSERT INTO data_rows (file_id, row_data) VALUES ($1, $2::jsonb)",
                    [(file_row_id, json.dumps(r)) for r in rows],
                )

        job.rows_ingested = len(rows)
        job.progress_pct = 100.0
        job.current_step = "done"
        job.status = IngestionStage.COMPLETED

    except Exception as exc:  # noqa: BLE001 - background task must never crash silently
        logger.exception("Ingestion job %s failed", job_id)
        job.status = IngestionStage.FAILED
        job.error = str(exc)
    finally:
        job.finished_at = datetime.now(timezone.utc)


@router.post("/ingest", response_model=IngestionStatusResponse)
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    dataset_label: str | None = None,
) -> IngestionStatusResponse:
    file_bytes = await file.read()
    job = IngestionStatusResponse.new(file_name=file.filename or "upload")
    _ingestion_jobs[job.job_id] = job

    background_tasks.add_task(
        _run_ingestion, job.job_id, file_bytes, job.file_name, dataset_label
    )
    return job


@router.get("/ingest/status", response_model=IngestionStatusResponse)
async def ingest_status(job_id: str) -> IngestionStatusResponse:
    job = _ingestion_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No ingestion job with id {job_id}")
    return job

