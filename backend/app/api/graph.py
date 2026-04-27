"""Graph API endpoints for semantic views."""

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.graph_response import GraphResponse
from backend.app.schemas.node_detail import NodeDetail
from backend.app.services.query.semantic_graph_reader import SemanticGraphFilters, SemanticGraphReader

router = APIRouter()
logger = logging.getLogger(__name__)

def _classify_graph_error(exc: Exception) -> tuple[int, str]:
    message = str(exc).lower()
    if "not found" in message:
        return (404, "Requested graph item was not found.")
    if "invalid" in message or "validation" in message:
        return (400, "Graph request validation failed.")
    if "timeout" in message or "unavailable" in message or "neo4j" in message:
        return (503, "Graph dependency is unavailable.")
    return (500, "Error retrieving semantic graph.")


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


def _build_semantic_graph(
    document_id: Optional[str] = None,
    node_types: Optional[List[str]] = Query(default=None),
    include_structural: bool = True,
    include_evidence: bool = False,
    include_citations: bool = False,
) -> GraphResponse:
    """Build semantic graph response with active semantic reader."""
    started_at = time.perf_counter()
    if document_id and ":" in document_id:
        logger.warning(
            "graph_api.legacy_document_id_received document_id=%s expected=document_uid",
            document_id,
        )
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
        if document_id and len(result.nodes) == 0:
            logger.warning(
                "Graph fetch returned empty for document scope document_id=%s filters=%s",
                document_id,
                result.meta.filters_applied,
            )
        if len(result.nodes) > 0 and len(result.edges) == 0:
            logger.warning(
                "Graph fetch returned nodes_without_edges document_id=%s node_count=%d",
                document_id,
                len(result.nodes),
            )
        return result
    except Exception as exc:
        status_code, detail = _classify_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/graph/semantic", response_model=GraphResponse)
async def get_semantic_graph(
    document_id: Optional[str] = None,
    node_types: Optional[List[str]] = Query(default=None),
    include_structural: bool = True,
    include_evidence: bool = False,
    include_citations: bool = False,
) -> GraphResponse:
    """Canonical semantic graph endpoint used by active runtime."""
    return _build_semantic_graph(
        document_id=document_id,
        node_types=node_types,
        include_structural=include_structural,
        include_evidence=include_evidence,
        include_citations=include_citations,
    )


@router.get("/graph/node/{node_id}", response_model=NodeDetail)
async def get_node_detail(node_id: str, document_id: Optional[str] = None) -> NodeDetail:
    """Return explainable inspector detail for a specific semantic node."""
    try:
        started_at = time.perf_counter()
        reader = SemanticGraphReader()
        detail = reader.read_node_detail(node_id=node_id, document_id=document_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Node not found")
        logger.info(
            "Node detail success node_id=%s document_id=%s incoming=%d outgoing=%d evidences=%d citations=%d elapsed=%.3fs",
            node_id,
            document_id,
            len(detail.grouped_relations.incoming),
            len(detail.grouped_relations.outgoing),
            len(detail.evidences),
            len(detail.citations),
            time.perf_counter() - started_at,
        )
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        status_code, detail = _classify_graph_error(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc
