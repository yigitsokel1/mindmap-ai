"""Semantic graph read service for visualization endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.graph_response import GraphEdge, GraphMeta, GraphNode, GraphResponse
from backend.app.schemas.node_detail import (
    NodeCitationItem,
    NodeDetail,
    NodeEvidenceItem,
    NodeRelationItem,
    NodeRelations,
)


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

    def read_node_detail(self, node_id: str, document_id: Optional[str] = None) -> Optional[NodeDetail]:
        node_record = self._load_node_by_id(node_id)
        if node_record is None:
            return None
        node = node_record.get("n")
        if node is None:
            return None

        node_type = self._primary_label(node)
        node_name = self._display_name(node)
        summary = str(node.get("summary") or node.get("description") or "")
        metadata = self._sanitize_metadata(dict(node.items()))
        incoming = self._load_relation_neighbors(node_id, direction="incoming", document_id=document_id)
        outgoing = self._load_relation_neighbors(node_id, direction="outgoing", document_id=document_id)
        evidences = self._load_node_evidences(node_id, document_id=document_id)
        citations = self._load_node_citations(node_id, document_id=document_id)

        return NodeDetail(
            id=node_id,
            type=node_type,
            name=node_name,
            summary=summary,
            metadata=metadata,
            relations=NodeRelations(incoming=incoming, outgoing=outgoing),
            evidences=evidences,
            citations=citations,
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
            OR any(key IN ['uid', 'id', 'document_id', 'doc_id'] WHERE n[key] = $document_id)
            OR EXISTS {
              MATCH (n)-[*1..4]-(d:Document)
              WHERE any(key IN ['uid', 'id', 'name'] WHERE d[key] = $document_id)
            }
          )
        RETURN DISTINCT n
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"labels": list(labels), "document_id": document_id, "limit": limit},
        )
        return records

    def _load_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        RETURN n
        LIMIT 1
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"node_id": node_id},
        )
        if not records:
            return None
        return records[0]

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

    def _load_relation_neighbors(
        self, node_id: str, direction: str, document_id: Optional[str], limit: int = 10
    ) -> List[NodeRelationItem]:
        if direction == "incoming":
            pattern = "(other)-[:OUT_REL]->(ri:RelationInstance)-[:TO]->(n)"
        else:
            pattern = "(n)-[:OUT_REL]->(ri:RelationInstance)-[:TO]->(other)"
        query = f"""
        MATCH (n)
        WHERE elementId(n) = $node_id
        MATCH {pattern}
        OPTIONAL MATCH (ev:Evidence)-[:SUPPORTS]->(ri)-[:TO]->(other)
        OPTIONAL MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
        OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p)
        WHERE $document_id IS NULL OR d.uid = $document_id
        RETURN DISTINCT other, ri
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"node_id": node_id, "document_id": document_id, "limit": limit},
        )
        relations: List[NodeRelationItem] = []
        for record in records:
            other = record.get("other")
            relation_instance = record.get("ri")
            if other is None:
                continue
            rel_type = relation_instance.get("type") if relation_instance else "RELATED_TO"
            relations.append(
                NodeRelationItem(
                    id=self._element_id(other),
                    type=str(rel_type),
                    name=self._display_name(other),
                )
            )
        return relations

    def _load_node_evidences(self, node_id: str, document_id: Optional[str], limit: int = 8) -> List[NodeEvidenceItem]:
        query = """
        MATCH (n)-[:OUT_REL]->(ri:RelationInstance)
        WHERE elementId(n) = $node_id
        OPTIONAL MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
        OPTIONAL MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
        OPTIONAL MATCH (sec:Section)-[:HAS_PASSAGE]->(p)
        OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p)
        WHERE $document_id IS NULL OR d.uid = $document_id
        RETURN DISTINCT ev, p, d, sec
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"node_id": node_id, "document_id": document_id, "limit": limit},
        )
        evidences: List[NodeEvidenceItem] = []
        for record in records:
            evidence = record.get("ev")
            passage = record.get("p")
            document = record.get("d")
            section = record.get("sec")
            text = ""
            if passage is not None:
                text = str(passage.get("text") or "")
            elif evidence is not None:
                text = str(evidence.get("text") or evidence.get("statement") or "")
            if not text:
                continue
            evidences.append(
                NodeEvidenceItem(
                    text=text[:420],
                    passage_id=self._element_id(passage) if passage is not None else "",
                    document_id=str(document.get("uid") or "") if document is not None else "",
                    section=str(section.get("title") or section.get("name") or "") if section is not None else None,
                    score=self._safe_float(evidence.get("confidence") if evidence is not None else None),
                )
            )
        return evidences

    def _load_node_citations(self, node_id: str, document_id: Optional[str], limit: int = 8) -> List[NodeCitationItem]:
        query = """
        MATCH (n)-[:OUT_REL]->(ri:RelationInstance)
        WHERE elementId(n) = $node_id
        MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
        MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
        OPTIONAL MATCH (p)-[:HAS_INLINE_CITATION]->(ic:InlineCitation)
        OPTIONAL MATCH (ic)-[:REFERS_TO]->(ref:ReferenceEntry)
        OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p)
        WHERE $document_id IS NULL OR d.uid = $document_id
        RETURN DISTINCT ic, ref
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"node_id": node_id, "document_id": document_id, "limit": limit},
        )
        citations: List[NodeCitationItem] = []
        seen: Set[str] = set()
        for record in records:
            inline = record.get("ic")
            reference = record.get("ref")
            if inline is None and reference is None:
                continue
            label = None
            title = ""
            year = None
            if inline is not None:
                labels = inline.get("reference_labels") or []
                label = str(labels[0]) if labels else inline.get("raw_text")
            if reference is not None:
                title = str(reference.get("title_guess") or reference.get("title") or "")
                year = self._safe_int(reference.get("year"))
                if not label:
                    label = (
                        reference.get("citation_key_numeric")
                        or reference.get("citation_key_author_year")
                        or None
                    )
            citation_key = f"{label}-{title}-{year}"
            if citation_key in seen:
                continue
            seen.add(citation_key)
            citations.append(NodeCitationItem(title=title or "reference", year=year, label=str(label) if label else None))
        return citations

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

    def _display_name(self, node: Any) -> str:
        props = dict(node.items())
        display_name = (
            props.get("display_name")
            or props.get("canonical_name")
            or props.get("name")
            or props.get("title")
            or props.get("id")
            or self._element_id(node)
        )
        return str(display_name)

    @staticmethod
    def _primary_label(node: Any) -> str:
        labels = list(getattr(node, "labels", []))
        return labels[0] if labels else "Node"

    @staticmethod
    def _sanitize_metadata(raw: Dict[str, Any]) -> Dict[str, str | int | float | bool | None]:
        clean: Dict[str, str | int | float | bool | None] = {}
        for key, value in raw.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean[key] = value
            else:
                clean[key] = str(value)
        return clean

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _element_id(entity: Any) -> str:
        if hasattr(entity, "element_id"):
            return str(entity.element_id)
        return str(entity.id)
