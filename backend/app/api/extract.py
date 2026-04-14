"""Extraction API endpoints for raw text testing."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.schemas.passage import PassageRecord
from backend.app.services.extraction.pipeline import ExtractionPipeline
from backend.app.services.parsing.passage_splitter import PassageSplitter

router = APIRouter()


class ExtractRequest(BaseModel):
    """Request model for extraction endpoint."""

    text: str
    document_id: str = "test_doc"


@router.post("/extract")
async def extract_text(request: ExtractRequest):
    """Run the extraction pipeline on raw text."""
    try:
        splitter = PassageSplitter()
        raw_passages = splitter.split(request.text)
        passages = [
            PassageRecord(
                passage_id=f"pass:{uuid.uuid4().hex[:12]}",
                document_id=request.document_id,
                index=i,
                text=text,
                page_number=0,
            )
            for i, text in enumerate(raw_passages)
        ]

        pipeline = ExtractionPipeline()
        result = pipeline.run(request.document_id, passages)

        return {
            "status": "ok",
            "document_id": result.document_id,
            "pages_total": result.pages_total,
            "passages_total": result.passages_total,
            "passages_succeeded": result.passages_succeeded,
            "passages_failed": result.passages_failed,
            "entities_total": result.entities_total,
            "relations_total": result.relations_total,
            "evidence_total": result.evidence_total,
            "entities_dropped": result.entities_dropped,
            "relations_dropped": result.relations_dropped,
            "errors": result.errors,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc
