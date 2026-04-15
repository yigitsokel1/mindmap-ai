"""Graph API endpoints for semantic views."""

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.graph_response import GraphResponse
from backend.app.services.query.semantic_graph_reader import SemanticGraphFilters, SemanticGraphReader

router = APIRouter()
logger = logging.getLogger(__name__)


def _normalize_node_types(node_types: Optional[List[str]]) -> List[str]:
    if not node_types:
        return []
    normalized: List[str] = []
    seen = set()
    for raw in node_types:
        for item in raw.split(","):
            value = item.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
    return normalized


@router.get("/graph", response_model=GraphResponse)
@router.get("/graph/semantic", response_model=GraphResponse)
async def get_semantic_graph(
    document_id: Optional[str] = None,
    node_types: Optional[List[str]] = Query(default=None),
    include_structural: bool = True,
    include_evidence: bool = False,
    include_citations: bool = False,
):
    """Return semantic graph view used as the default read path."""
    started_at = time.perf_counter()
    try:
        reader = SemanticGraphReader()
        filters = SemanticGraphFilters(
            document_id=document_id,
            node_types=_normalize_node_types(node_types),
            include_structural=include_structural,
            include_evidence=include_evidence,
            include_citations=include_citations,
        )
        result = reader.read_graph(filters)
        logger.info(
            "Graph fetch summary document_id=%s node_types=%s structural=%s evidence=%s citations=%s nodes=%d edges=%d elapsed=%.3fs",
            document_id,
            filters.node_types,
            include_structural,
            include_evidence,
            include_citations,
            len(result.nodes),
            len(result.edges),
            time.perf_counter() - started_at,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error retrieving semantic graph: {exc}") from exc
