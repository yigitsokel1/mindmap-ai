"""Legacy retrieval service shim.

This module isolates legacy retrieval imports under services/legacy.
"""

from backend.app.services.retrieval import GraphRAGService

__all__ = ["GraphRAGService"]
