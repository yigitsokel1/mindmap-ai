"""Compatibility shim for quarantined legacy ingestion service.

Removal marker:
    - status: scheduled_for_removal
    - target: Sprint 18
    - replacement: backend.app.legacy.services.ingestion.legacy_ingestion_service.IngestionService
"""

from backend.app.legacy.services.ingestion.legacy_ingestion_service import IngestionService

__all__ = ["IngestionService"]
