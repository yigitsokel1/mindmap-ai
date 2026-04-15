"""Compatibility shim for quarantined legacy retrieval implementation.

Removal marker:
    - status: scheduled_for_removal
    - target: Sprint 18
    - replacement: backend.app.legacy.services.legacy.retrieval.GraphRAGService
"""

from backend.app.legacy.services.legacy.retrieval import GraphRAGService

__all__ = ["GraphRAGService"]
