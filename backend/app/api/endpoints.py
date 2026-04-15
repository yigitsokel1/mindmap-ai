"""Legacy compatibility shim for split API router.

Removal marker:
    - status: scheduled_for_removal
    - target: Sprint 18
    - replacement: backend.app.api.router

Import compatibility only; do not add new routes here.
"""

from backend.app.api.router import router

# Pydantic models for request bodies
__all__ = ["router"]
