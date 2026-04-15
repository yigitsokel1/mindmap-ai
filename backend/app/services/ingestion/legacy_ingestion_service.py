"""Compatibility shim for quarantined legacy ingestion service."""

from backend.app.legacy.services.ingestion.legacy_ingestion_service import IngestionService

__all__ = ["IngestionService"]
