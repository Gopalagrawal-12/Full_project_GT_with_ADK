"""
api/router.py
----------------
Combines every feature-specific router (tabular ingest, document ingest,
chat) into a single `APIRouter` that main.py mounts once, under one
versioned prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.chat_routes import router as chat_router
from api.ingest_routes import router as ingest_router
from api.vector_ingest_routes import router as vector_ingest_router

router = APIRouter()
router.include_router(ingest_router)
router.include_router(vector_ingest_router)
router.include_router(chat_router)
