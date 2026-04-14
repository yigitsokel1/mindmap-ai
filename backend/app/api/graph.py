"""Graph API endpoints for semantic and legacy views."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.graph_response import GraphResponse
from backend.app.services.query.semantic_graph_reader import SemanticGraphFilters, SemanticGraphReader

router = APIRouter()


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
    try:
        reader = SemanticGraphReader()
        filters = SemanticGraphFilters(
            document_id=document_id,
            node_types=_normalize_node_types(node_types),
            include_structural=include_structural,
            include_evidence=include_evidence,
            include_citations=include_citations,
        )
        return reader.read_graph(filters)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error retrieving semantic graph: {exc}") from exc


@router.get("/graph/legacy")
async def get_legacy_graph(node_ids: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Return legacy Document/Chunk graph format."""
    db = Neo4jDatabase()
    if not db.driver:
        db.connect()

    try:
        if node_ids:
            node_id_list = [node_id.strip() for node_id in node_ids.split(",") if node_id.strip()]
            node_query = """
            UNWIND $node_ids AS node_id
            MATCH (n)
            WHERE elementId(n) = node_id
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN DISTINCT n, r, m
            LIMIT 5000
            """
            records, _, _ = db.driver.execute_query(  # type: ignore[union-attr]
                node_query,
                {"node_ids": node_id_list},
                database_="neo4j",
            )
        else:
            query = """
            MATCH (n)
            WHERE n:Document OR n:Chunk
            OPTIONAL MATCH (n)-[r:BELONGS_TO]-(m)
            RETURN DISTINCT n, r, m
            LIMIT 5000
            """
            records, _, _ = db.driver.execute_query(query, database_="neo4j")  # type: ignore[union-attr]

        nodes_map: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []
        seen_links = set()
        for record in records:
            node_n = record.get("n")
            rel = record.get("r")
            node_m = record.get("m")

            if node_n is not None:
                _add_legacy_node(nodes_map, node_n)
            if node_m is not None:
                _add_legacy_node(nodes_map, node_m)
            if rel is not None and node_n is not None and node_m is not None:
                source_id = _element_id(node_n)
                target_id = _element_id(node_m)
                link_key = (source_id, target_id, getattr(rel, "type", "RELATED_TO"))
                if link_key in seen_links:
                    continue
                seen_links.add(link_key)
                links.append(
                    {
                        "source": source_id,
                        "target": target_id,
                        "type": getattr(rel, "type", "RELATED_TO"),
                    }
                )

        return {"nodes": list(nodes_map.values()), "links": links}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error retrieving legacy graph: {exc}") from exc


def _add_legacy_node(nodes_map: Dict[str, Dict[str, Any]], node: Any) -> None:
    node_id = _element_id(node)
    if node_id in nodes_map:
        return

    labels = list(getattr(node, "labels", []))
    props = dict(node.items())
    node_type = labels[0] if labels else "Node"
    node_name = props.get("id") or props.get("name") or props.get("title") or node_id
    node_data: Dict[str, Any] = {
        "id": node_id,
        "label": node_type,
        "name": node_name,
        "type": node_type.lower(),
    }
    if node_type == "Chunk":
        if "page" in props:
            node_data["page"] = props["page"]
        if "source" in props:
            node_data["source"] = props["source"]
    nodes_map[node_id] = node_data


def _element_id(entity: Any) -> str:
    if hasattr(entity, "element_id"):
        return str(entity.element_id)
    return str(entity.id)
