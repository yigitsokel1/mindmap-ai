"""Semantic grounded query endpoints."""

from fastapi import APIRouter, HTTPException

from backend.app.schemas.semantic_query import SemanticQueryAnswer, SemanticQueryRequest
from backend.app.services.query.semantic_query_service import SemanticQueryService

router = APIRouter()


@router.post("/query/semantic", response_model=SemanticQueryAnswer)
async def semantic_query(request: SemanticQueryRequest) -> SemanticQueryAnswer:
    """Answer a semantic question using evidence-backed graph retrieval."""
    try:
        service = SemanticQueryService()
        return service.answer(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error processing semantic query: {exc}") from exc
