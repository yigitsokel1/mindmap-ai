"""Semantic query endpoints."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.schemas.semantic_query import SemanticQueryAnswer, SemanticQueryRequest
from backend.app.core.security import enforce_query_rate_limit, require_api_key
from backend.app.services.query.semantic_query_service import (
    SemanticQueryService,
    SemanticQueryServiceError,
)

router = APIRouter()
logger = logging.getLogger(__name__)

ERROR_TO_STATUS = {
    "validation_error": (400, "Request validation failed."),
    "dependency_error": (503, "A required backend dependency is currently unavailable."),
    "not_found": (404, "Requested semantic resources were not found."),
    "partial_data": (206, "Query completed with partial data."),
}


@router.post("/query/semantic", response_model=SemanticQueryAnswer)
async def semantic_query(
    request: SemanticQueryRequest,
    http_request: Request,
    _api_key: None = Depends(require_api_key),
) -> SemanticQueryAnswer:
    """Answer a semantic question using evidence-backed graph retrieval."""
    started_at = time.perf_counter()
    enforce_query_rate_limit(http_request)
    try:
        service = SemanticQueryService()
        response = service.answer(request)
        evidence_count = len(response.evidence) if hasattr(response, "evidence") else len(response.get("evidence", []))
        related_count = (
            len(response.related_nodes)
            if hasattr(response, "related_nodes")
            else len(response.get("related_nodes", []))
        )
        logger.info(
            "Semantic query success question_len=%d document_id=%s node_types=%s max_evidence=%d include_citations=%s evidence=%d related_nodes=%d elapsed=%.3fs",
            len(request.question),
            request.document_id,
            request.node_types,
            request.max_evidence,
            request.include_citations,
            evidence_count,
            related_count,
            time.perf_counter() - started_at,
        )
        return response
    except SemanticQueryServiceError as exc:
        logger.error(
            "Semantic query failure question_len=%d document_id=%s error=%s",
            len(request.question),
            request.document_id,
            exc,
            exc_info=True,
        )
        status_code, detail = ERROR_TO_STATUS.get(exc.category, (500, "Semantic query processing failed. Please try again."))
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        logger.error("Unexpected semantic query failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Unexpected semantic query failure.",
        ) from exc
