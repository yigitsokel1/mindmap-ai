"""Compatibility shim for the split API router."""

from backend.app.api.router import router

# Pydantic models for request bodies
__all__ = ["router"]
