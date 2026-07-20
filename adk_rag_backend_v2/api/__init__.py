"""
api package
-------------
router.py aggregates ingest_routes.py + chat_routes.py into a single
APIRouter that main.py mounts under /api/v1.
"""

from api.router import router

__all__ = ["router"]
