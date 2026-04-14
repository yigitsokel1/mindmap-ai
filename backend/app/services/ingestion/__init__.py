# Re-export IngestionService for backward compatibility
from backend.app.services.ingestion.legacy_ingestion_service import IngestionService

__all__ = ["IngestionService"]
