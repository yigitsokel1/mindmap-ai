"""Legacy compatibility shim for split API router.

Import compatibility only; do not add new routes here.
"""

from backend.app.api.router import router

# Pydantic models for request bodies
__all__ = ["router"]
