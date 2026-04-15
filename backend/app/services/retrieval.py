"""Compatibility shim for legacy retrieval service.

Legacy runtime lives under backend.app.legacy and is quarantined from active API paths.
"""

from backend.app.legacy.services.retrieval import GraphRAGService

__all__ = ["GraphRAGService"]
