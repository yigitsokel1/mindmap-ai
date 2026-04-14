"""Semantic graph read service for visualization endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.graph_response import GraphEdge, GraphMeta, GraphNode, GraphResponse


@dataclass(frozen=True)
class SemanticGraphFilters:
    document_id: Optional[str]
    node_types: List[str]
    include_structural: bool
    include_evidence: bool
    include_citations: bool


class SemanticGraphReader:
    """Reads semantic graph data from Neo4j and maps to API contract."""

    BASE_NODE_TYPES: Set[str] = {
        "Method",
        "Concept",
        "Dataset",
        "Metric",
        "Task",
        "Author",
        "Institution",
        "RelationInstance",
    }
    STRUCTURAL_NODE_TYPES: Set[str] = {"Document", "Section"}
    EVIDENCE_NODE_TYPES: Set[str] = {"Passage", "Evidence"}
    CITATION_NODE_TYPES: Set[str] = {"ReferenceEntry", "InlineCitation"}
    SUPPORTED_NODE_TYPES: Set[str] = (
        BASE_NODE_TYPES | STRUCTURAL_NODE_TYPES | EVIDENCE_NODE_TYPES | CITATION_NODE_TYPES
    )

    def __init__(self) -> None:
        self.db = Neo4jDatabase()
        if not self.db.driver:
            self.db.connect()

    def read_graph(self, filters: SemanticGraphFilters, limit: int = 2500) -> GraphResponse:
        included_labels = self._resolve_labels(filters)
        records = self._load_nodes(included_labels, filters.document_id, limit)
        node_by_id: Dict[str, GraphNode] = {}
        node_ids: List[str] = []
        for record in records:
            node = record.get("n")
            if node is None:
                continue
            node_id = self._element_id(node)
            if node_id in node_by_id:
                continue
            model = self._map_node(node)
            node_by_id[node_id] = model
            node_ids.append(node_id)

        edges = self._load_edges(node_ids)
        return GraphResponse(
            nodes=list(node_by_id.values()),
            edges=edges,
            meta=GraphMeta(
                counts={
                    "nodes": len(node_by_id),
                    "edges": len(edges),
                },
                filters_applied={
                    "document_id": filters.document_id,
                    "node_types": filters.node_types,
                    "include_structural": filters.include_structural,
                    "include_evidence": filters.include_evidence,
                    "include_citations": filters.include_citations,
                    "effective_node_types": sorted(included_labels),
                },
            ),
        )

    def _resolve_labels(self, filters: SemanticGraphFilters) -> Set[str]:
        labels = set(self.BASE_NODE_TYPES)
        if filters.include_structural:
            labels |= self.STRUCTURAL_NODE_TYPES
        if filters.include_evidence:
            labels |= self.EVIDENCE_NODE_TYPES
        if filters.include_citations:
            labels |= self.CITATION_NODE_TYPES

        if filters.node_types:
            requested = {node_type for node_type in filters.node_types if node_type in self.SUPPORTED_NODE_TYPES}
            if requested:
                labels &= requested
        return labels

    def _load_nodes(self, labels: Iterable[str], document_id: Optional[str], limit: int) -> List[Dict[str, Any]]:
        query = """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN $labels)
          AND (
            $document_id IS NULL
            OR n.id = $document_id
            OR n.document_id = $document_id
            OR n.doc_id = $document_id
            OR EXISTS {
              MATCH (n)-[*1..4]-(d:Document)
              WHERE d.id = $document_id OR d.uid = $document_id OR d.name = $document_id
            }
          )
        RETURN DISTINCT n
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"labels": list(labels), "document_id": document_id, "limit": limit},
            database_="neo4j",
        )
        return records

    def _load_edges(self, node_ids: List[str]) -> List[GraphEdge]:
        if not node_ids:
            return []

        query = """
        UNWIND $node_ids AS source_id
        MATCH (a)
        WHERE elementId(a) = source_id
        MATCH (a)-[r]->(b)
        WHERE elementId(b) IN $node_ids
        RETURN DISTINCT a, r, b
        LIMIT 10000
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"node_ids": node_ids},
            database_="neo4j",
        )

        edges: List[GraphEdge] = []
        seen: Set[str] = set()
        for record in records:
            rel = record.get("r")
            source = record.get("a")
            target = record.get("b")
            if rel is None or source is None or target is None:
                continue
            edge_id = self._element_id(rel)
            if edge_id in seen:
                continue
            seen.add(edge_id)
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source=self._element_id(source),
                    target=self._element_id(target),
                    type=getattr(rel, "type", "RELATED_TO"),
                    properties=dict(rel.items()),
                )
            )
        return edges

    def _map_node(self, node: Any) -> GraphNode:
        labels = list(getattr(node, "labels", []))
        node_type = labels[0] if labels else "Node"
        props = dict(node.items())
        display_name = (
            props.get("display_name")
            or props.get("canonical_name")
            or props.get("name")
            or props.get("title")
            or props.get("id")
            or self._element_id(node)
        )
        return GraphNode(
            id=self._element_id(node),
            label=node_type,
            type=node_type,
            display_name=str(display_name),
            properties=props,
        )

    @staticmethod
    def _element_id(entity: Any) -> str:
        if hasattr(entity, "element_id"):
            return str(entity.element_id)
        return str(entity.id)
