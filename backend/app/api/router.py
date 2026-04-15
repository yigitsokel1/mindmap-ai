"""Top-level API router composition."""

from fastapi import APIRouter

from backend.app.api.chat import router as chat_router
from backend.app.api.extract import router as extract_router
from backend.app.api.graph import router as graph_router
from backend.app.api.ingest import router as ingest_router
from backend.app.api.query import router as query_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(ingest_router)
router.include_router(extract_router)
router.include_router(graph_router)
router.include_router(query_router)
