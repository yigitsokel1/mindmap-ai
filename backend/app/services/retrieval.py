"""Compatibility shim for legacy retrieval service.

Legacy runtime lives under backend.app.legacy and is quarantined from active API paths.

Removal marker:
    - status: scheduled_for_removal
    - target: Sprint 18
    - replacement: backend.app.legacy.services.retrieval.GraphRAGService
"""

from backend.app.legacy.services.retrieval import GraphRAGService

__all__ = ["GraphRAGService"]
