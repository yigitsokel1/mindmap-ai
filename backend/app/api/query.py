"""Semantic grounded query endpoints."""

import logging
import time

from fastapi import APIRouter, HTTPException

from backend.app.schemas.semantic_query import SemanticQueryAnswer, SemanticQueryRequest
from backend.app.services.query.semantic_query_service import (
    SemanticQueryService,
    SemanticQueryServiceError,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/query/semantic", response_model=SemanticQueryAnswer)
async def semantic_query(request: SemanticQueryRequest) -> SemanticQueryAnswer:
    """Answer a semantic question using evidence-backed graph retrieval."""
    started_at = time.perf_counter()
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
            "Semantic query success question_len=%d document_id=%s evidence=%d related_nodes=%d elapsed=%.3fs",
            len(request.question),
            request.document_id,
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
        raise HTTPException(
            status_code=500,
            detail="Semantic query processing failed. Please try again.",
        ) from exc
    except Exception as exc:
        logger.error("Unexpected semantic query failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Unexpected semantic query failure.",
        ) from exc
