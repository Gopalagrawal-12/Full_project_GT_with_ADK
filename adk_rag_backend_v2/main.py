"""
main.py
--------
Central FastAPI entrypoint. Owns the application lifecycle: pool allocation
at startup, graceful teardown at shutdown, global CORS policy, and router
registration under a versioned prefix.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import router as api_router
from utils.db_pool import close_pool, init_pool
from utils.db_schema_bootstrap import ensure_schema
from dotenv import load_dotenv

# 1. Load env vars first
load_dotenv()

# 2. Apply the network patch IMMEDIATELY
from utils.gemini_pool import apply_adk_patch
apply_adk_patch()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("adk_rag.main")

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: allocating asyncpg connection pool...")
    await init_pool()
    await ensure_schema()
    logger.info("Startup complete.")

    yield

    logger.info("Shutting down: closing asyncpg connection pool...")
    await close_pool()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Multi-Agent ADK RAG Backend",
    description="Async Multi-Agent Text-to-SQL & Vector RAG backend on Google ADK.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1", tags=["rag"])


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
