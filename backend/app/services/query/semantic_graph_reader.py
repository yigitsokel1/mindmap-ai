"""Semantic graph read service for visualization endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, Iterable, List, Optional, Set

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.graph_response import GraphEdge, GraphMeta, GraphNode, GraphResponse
from backend.app.schemas.node_detail import (
    NodeCitationItem,
    NodeDetail,
    NodeEvidenceItem,
    NodeGroupedRelations,
    NodeRelationGroup,
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
        "CanonicalEntity",
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
        self.logger = logging.getLogger(__name__)

    def read_graph(self, filters: SemanticGraphFilters, limit: int = 2500) -> GraphResponse:
        included_labels = self._resolve_labels(filters)
        self._warn_if_legacy_document_scope(filters.document_id)
        self.logger.info(
            "graph_reader.start document_id=%s node_types=%s effective_labels=%s include_structural=%s include_evidence=%s include_citations=%s",
            filters.document_id,
            filters.node_types,
            sorted(included_labels),
            filters.include_structural,
            filters.include_evidence,
            filters.include_citations,
        )
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

        in_scope_node_ids = self._load_in_scope_node_ids(node_ids, filters.document_id)
        edges = self._load_edges(node_ids, in_scope_node_ids=in_scope_node_ids)
        in_scope_edge_count = sum(1 for edge in edges if edge.properties.get("edge_scope") == "in_scope")
        bridged_edge_count = sum(1 for edge in edges if edge.properties.get("edge_scope") == "bridged")
        if node_ids and not edges:
            self.logger.warning(
                "graph_reader.suspicious nodes_present_without_edges document_id=%s node_count=%d",
                filters.document_id,
                len(node_ids),
            )
        if filters.document_id and not node_ids:
            self.logger.warning("graph_reader.empty_for_document_scope document_id=%s", filters.document_id)
        return GraphResponse(
            nodes=list(node_by_id.values()),
            edges=edges,
            meta=GraphMeta(
                counts={
                    "nodes": len(node_by_id),
                    "edges": len(edges),
                    "in_scope_nodes": len(in_scope_node_ids) if filters.document_id else len(node_by_id),
                    "in_scope_edges": in_scope_edge_count if filters.document_id else len(edges),
                    "bridged_edges": bridged_edge_count if filters.document_id else 0,
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
        metadata = self._sanitize_metadata(dict(node.items()))
        incoming = self._load_relation_neighbors(node_id, direction="incoming", document_id=document_id)
        outgoing = self._load_relation_neighbors(node_id, direction="outgoing", document_id=document_id)
        evidences = self._load_node_evidences(node_id, document_id=document_id)
        citations = self._load_node_citations(node_id, document_id=document_id)
        grouped_relations = NodeGroupedRelations(
            incoming=self._group_relations(incoming),
            outgoing=self._group_relations(outgoing),
        )
        canonical_info = self._load_canonical_details(node_id)
        summary = self._build_node_summary(
            node_type=node_type,
            node_name=node_name,
            incoming=incoming,
            outgoing=outgoing,
            evidences=evidences,
            citations=citations,
            metadata=metadata,
            canonical_info=canonical_info,
        )

        return NodeDetail(
            id=node_id,
            type=node_type,
            name=node_name,
            summary=summary,
            metadata=metadata,
            relations=NodeRelations(incoming=incoming, outgoing=outgoing),
            grouped_relations=grouped_relations,
            evidences=evidences,
            citations=citations,
            linked_canonical_entity=canonical_info.get("canonical"),
            canonical_link_reason=canonical_info.get("link_reason"),
            canonical_link_confidence=canonical_info.get("link_confidence"),
            canonical_aliases=canonical_info.get("aliases", []),
            canonical_alias_count=int(canonical_info.get("alias_count", 0)),
            appears_in_documents=int(canonical_info.get("document_count", 0)),
            top_related_documents=canonical_info.get("top_documents", []),
            document_distribution=canonical_info.get("document_distribution", []),
        )

    # Query candidate reads (extension-ready for canonical linking)
    def read_candidate_entities(
        self,
        tokens: List[str],
        document_id: Optional[str] = None,
        node_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Read candidate semantic nodes for query-time selection."""
        if not tokens:
            return []
        query = """
        MATCH (n)
        WHERE any(lbl IN labels(n) WHERE lbl IN ['Author', 'Institution', 'Concept', 'Method', 'Dataset', 'Metric', 'Task'])
          AND (
            size($node_types) = 0
            OR any(label IN labels(n) WHERE label IN $node_types)
          )
          AND (
            $document_id IS NULL
            OR EXISTS {
                MATCH (n)-[:OUT_REL]->(:RelationInstance)<-[:SUPPORTS]-(:Evidence)-[:FROM_PASSAGE]->(:Passage)<-[:HAS_PASSAGE]-(:Section)<-[:HAS_SECTION]-(d:Document {uid: $document_id})
            }
          )
          AND any(token IN $tokens WHERE
            toLower(coalesce(n.canonical_name, "")) CONTAINS token
            OR toLower(coalesce(n.name, "")) CONTAINS token
            OR toLower(coalesce(n.title, "")) CONTAINS token
          )
        RETURN DISTINCT n
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {
                "tokens": [token.lower() for token in tokens],
                "document_id": document_id,
                "node_types": node_types or [],
                "limit": limit,
            },
        )
        return records

    def read_canonical_lookup_candidates(self, tokens: List[str]) -> List[Dict[str, Any]]:
        """Read local entities via canonical name and alias lookup."""
        if not tokens:
            return []
        query = """
        MATCH (e)-[:INSTANCE_OF_CANONICAL]->(c:CanonicalEntity)
        WHERE any(token IN $tokens WHERE
            toLower(coalesce(c.canonical_name, "")) CONTAINS token
            OR token IN coalesce(c.normalized_aliases, [])
            OR token IN coalesce(c.acronyms, [])
        )
        RETURN DISTINCT e, c
        LIMIT 20
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"tokens": [token.lower() for token in tokens]},
        )
        return records

    def _load_canonical_details(self, node_id: str) -> Dict[str, Any]:
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        OPTIONAL MATCH (n)-[:INSTANCE_OF_CANONICAL]->(c:CanonicalEntity)
        OPTIONAL MATCH (n)-[icl:INSTANCE_OF_CANONICAL]->(c)
        OPTIONAL MATCH (peer)-[:INSTANCE_OF_CANONICAL]->(c)
        OPTIONAL MATCH (peer)-[:OUT_REL]->(:RelationInstance)<-[:SUPPORTS]-(:Evidence)-[:FROM_PASSAGE]->(:Passage)<-[:HAS_PASSAGE]-(:Section)<-[:HAS_SECTION]-(d:Document)
        WITH c, icl, collect(DISTINCT d.title) AS doc_titles, count(DISTINCT d) AS doc_count
        RETURN c, icl, doc_titles, doc_count
        LIMIT 1
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"node_id": node_id},
        )
        if not records:
            return {
                "canonical": None,
                "aliases": [],
                "alias_count": 0,
                "document_count": 0,
                "top_documents": [],
                "document_distribution": [],
                "link_reason": None,
                "link_confidence": None,
            }
        record = records[0]
        canonical = record.get("c")
        if canonical is None:
            return {
                "canonical": None,
                "aliases": [],
                "alias_count": 0,
                "document_count": 0,
                "top_documents": [],
                "document_distribution": [],
                "link_reason": None,
                "link_confidence": None,
            }
        canonical_payload = {
            "uid": str(canonical.get("uid") or ""),
            "entity_type": str(canonical.get("entity_type") or ""),
            "canonical_name": str(canonical.get("canonical_name") or ""),
        }
        doc_titles = [str(item) for item in record.get("doc_titles", []) if item]
        aliases = [str(item) for item in canonical.get("aliases", []) if item]
        return {
            "canonical": canonical_payload,
            "aliases": aliases[:12],
            "alias_count": len(aliases),
            "document_count": int(record.get("doc_count") or 0),
            "top_documents": doc_titles[:5],
            "document_distribution": [
                {"document": title, "count": 1}
                for title in doc_titles[:3]
            ],
            "link_reason": str(canonical.get("link_reason") or (record.get("icl") or {}).get("reason") or ""),
            "link_confidence": self._safe_float(
                canonical.get("link_confidence") or (record.get("icl") or {}).get("confidence")
            ),
        }

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
            OR any(key IN ['uid', 'id', 'document_id', 'doc_id', 'source_document_id'] WHERE n[key] = $document_id)
            OR EXISTS {
              MATCH (n)-[*1..4]-(d:Document)
              WHERE d.uid = $document_id
                 OR ($allow_legacy_element_id AND elementId(d) = $document_id)
            }
            OR EXISTS {
              MATCH (n)-[:INSTANCE_OF_CANONICAL]->(:CanonicalEntity)<-[:INSTANCE_OF_CANONICAL]-(peer)-[*1..4]-(d:Document)
              WHERE d.uid = $document_id
                 OR ($allow_legacy_element_id AND elementId(d) = $document_id)
            }
          )
        RETURN DISTINCT n
        LIMIT $limit
        """
        allow_legacy_element_id = self._is_legacy_element_id(document_id)
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {
                "labels": list(labels),
                "document_id": document_id,
                "limit": limit,
                "allow_legacy_element_id": allow_legacy_element_id,
            },
        )
        self.logger.info(
            "graph_reader.nodes_loaded document_id=%s labels=%d count=%d limit=%d",
            document_id,
            len(list(labels)),
            len(records),
            limit,
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

    def _load_edges(self, node_ids: List[str], in_scope_node_ids: Optional[Set[str]] = None) -> List[GraphEdge]:
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
            properties = dict(rel.items())
            if in_scope_node_ids is not None:
                source_id = self._element_id(source)
                target_id = self._element_id(target)
                properties["edge_scope"] = (
                    "in_scope" if source_id in in_scope_node_ids and target_id in in_scope_node_ids else "bridged"
                )
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source=self._element_id(source),
                    target=self._element_id(target),
                    type=getattr(rel, "type", "RELATED_TO"),
                    properties=properties,
                )
            )
        return edges

    def _load_relation_neighbors(
        self, node_id: str, direction: str, document_id: Optional[str], limit: int = 10
    ) -> List[NodeRelationItem]:
        if direction == "incoming":
            pattern = "(other)-[rel]->(n)"
        else:
            pattern = "(n)-[rel]->(other)"
        query = f"""
        MATCH (n)
        WHERE elementId(n) = $node_id
        MATCH {pattern}
        WHERE elementId(other) <> $node_id
          AND (
            $document_id IS NULL
            OR EXISTS {{
              MATCH (other)-[*1..4]-(d:Document)
              WHERE elementId(d) = $document_id
                 OR any(key IN ['uid', 'id', 'name'] WHERE d[key] = $document_id)
            }}
          )
        RETURN DISTINCT other, rel
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"node_id": node_id, "document_id": document_id, "limit": limit},
        )
        relations: List[NodeRelationItem] = []
        for record in records:
            other = record.get("other")
            rel = record.get("rel")
            if other is None:
                continue
            rel_type = getattr(rel, "type", None) or "RELATED_TO"
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
        MATCH (n)
        WHERE elementId(n) = $node_id
        CALL () {
          WITH $node_id AS node_id
          MATCH (src)
          WHERE elementId(src) = node_id
          MATCH (src)-[:OUT_REL]->(ri:RelationInstance)
          RETURN ri
          UNION
          WITH $node_id AS node_id
          MATCH (dst)
          WHERE elementId(dst) = node_id
          MATCH (ri:RelationInstance)-[:TO]->(dst)
          RETURN ri
          UNION
          WITH $node_id AS node_id
          MATCH (ri:RelationInstance)
          WHERE elementId(ri) = node_id
          RETURN ri
        }
        OPTIONAL MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
        OPTIONAL MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
        OPTIONAL MATCH (sec:Section)-[:HAS_PASSAGE]->(p)
        OPTIONAL MATCH (d:Document)
        WHERE (
          EXISTS { MATCH (d)-[:HAS_PASSAGE]->(p) }
          OR EXISTS { MATCH (d)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p) }
        )
          AND (
            $document_id IS NULL
            OR elementId(d) = $document_id
            OR any(key IN ['uid', 'id', 'name'] WHERE d[key] = $document_id)
          )
        WITH ev, p, d, sec
        WHERE (ev IS NOT NULL OR p IS NOT NULL)
          AND ($document_id IS NULL OR d IS NOT NULL)
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
                    document_name=str(document.get("title") or document.get("file_name") or "") if document is not None else None,
                    page=self._safe_int(passage.get("page_number")) if passage is not None else None,
                    section=str(section.get("title") or section.get("name") or "") if section is not None else None,
                    score=self._safe_float(evidence.get("confidence") if evidence is not None else None),
                )
            )
        return evidences

    def _load_in_scope_node_ids(self, node_ids: List[str], document_id: Optional[str]) -> Set[str]:
        if not node_ids:
            return set()
        if not document_id:
            return set(node_ids)
        query = """
        UNWIND $node_ids AS node_id
        MATCH (n)
        WHERE elementId(n) = node_id
          AND (
            any(key IN ['uid', 'id', 'document_id', 'doc_id', 'source_document_id'] WHERE n[key] = $document_id)
            OR EXISTS {
              MATCH (n)-[*1..4]-(d:Document)
              WHERE d.uid = $document_id
                 OR ($allow_legacy_element_id AND elementId(d) = $document_id)
            }
          )
        RETURN DISTINCT elementId(n) AS node_id
        """
        allow_legacy_element_id = self._is_legacy_element_id(document_id)
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {
                "node_ids": node_ids,
                "document_id": document_id,
                "allow_legacy_element_id": allow_legacy_element_id,
            },
        )
        return {str(record.get("node_id")) for record in records if record.get("node_id")}

    @staticmethod
    def _is_legacy_element_id(document_id: Optional[str]) -> bool:
        if not document_id:
            return False
        return ":" in document_id

    def _warn_if_legacy_document_scope(self, document_id: Optional[str]) -> None:
        if self._is_legacy_element_id(document_id):
            self.logger.warning(
                "graph_reader.legacy_document_scope_id document_id=%s expected=document_uid", document_id
            )

    def _load_node_citations(self, node_id: str, document_id: Optional[str], limit: int = 8) -> List[NodeCitationItem]:
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        CALL () {
          WITH $node_id AS node_id
          MATCH (src)
          WHERE elementId(src) = node_id
          MATCH (src)-[:OUT_REL]->(ri:RelationInstance)
          RETURN ri
          UNION
          WITH $node_id AS node_id
          MATCH (dst)
          WHERE elementId(dst) = node_id
          MATCH (ri:RelationInstance)-[:TO]->(dst)
          RETURN ri
          UNION
          WITH $node_id AS node_id
          MATCH (ri:RelationInstance)
          WHERE elementId(ri) = node_id
          RETURN ri
        }
        MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
        MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
        OPTIONAL MATCH (p)-[:HAS_INLINE_CITATION]->(ic:InlineCitation)
        OPTIONAL MATCH (ic)-[:REFERS_TO]->(ref:ReferenceEntry)
        OPTIONAL MATCH (d:Document)
        WHERE (
          EXISTS { MATCH (d)-[:HAS_PASSAGE]->(p) }
          OR EXISTS { MATCH (d)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p) }
        )
          AND (
            $document_id IS NULL
            OR elementId(d) = $document_id
            OR any(key IN ['uid', 'id', 'name'] WHERE d[key] = $document_id)
          )
        WITH ic, ref, d
        WHERE $document_id IS NULL OR d IS NOT NULL
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
            props.get("name")
            or props.get("title")
            or props.get("display_name")
            or props.get("canonical_name")
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
            props.get("name")
            or props.get("title")
            or props.get("display_name")
            or props.get("canonical_name")
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
    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _group_relations(relations: List[NodeRelationItem]) -> List[NodeRelationGroup]:
        grouped: Dict[str, List[NodeRelationItem]] = {}
        for relation in relations:
            grouped.setdefault(relation.type, []).append(relation)
        items: List[NodeRelationGroup] = []
        for relation_type, members in grouped.items():
            items.append(
                NodeRelationGroup(
                    relation_type=relation_type,
                    count=len(members),
                    items=members,
                )
            )
        items.sort(key=lambda group: group.count, reverse=True)
        return items

    @staticmethod
    def _build_node_summary(
        node_type: str,
        node_name: str,
        incoming: List[NodeRelationItem],
        outgoing: List[NodeRelationItem],
        evidences: List[NodeEvidenceItem],
        citations: List[NodeCitationItem],
        metadata: Dict[str, str | int | float | bool | None],
        canonical_info: Dict[str, Any],
    ) -> str:
        total_relations = len(incoming) + len(outgoing)
        top_outgoing = outgoing[0].type if outgoing else "none"
        top_incoming = incoming[0].type if incoming else "none"
        docs = sorted({e.document_id for e in evidences if e.document_id})
        doc_hint = f"{len(docs)} document(s)" if docs else "no linked documents"
        importance_score = total_relations + len(evidences) + (2 * len(citations))
        priority = "high" if importance_score >= 10 else "medium" if importance_score >= 5 else "low"
        existing_summary = str(metadata.get("summary") or metadata.get("description") or "").strip()
        canonical_hint = ""
        canonical_payload = canonical_info.get("canonical")
        if canonical_payload:
            canonical_hint = (
                f" Canonical identity '{canonical_payload.get('canonical_name', 'unknown')}' is linked "
                f"across {int(canonical_info.get('document_count', 0))} document(s)."
            )
        if existing_summary:
            return (
                f"{existing_summary} Node '{node_name}' ({node_type}) has {total_relations} relation(s), "
                f"dominant outgoing '{top_outgoing}', dominant incoming '{top_incoming}', appears in {doc_hint}, "
                f"and has {priority} explainability importance based on relation/evidence/citation density."
                f"{canonical_hint}"
            )
        return (
            f"Node '{node_name}' is a {node_type} with {total_relations} relation(s). "
            f"Dominant outgoing relation is '{top_outgoing}' and dominant incoming relation is '{top_incoming}'. "
            f"It appears in {doc_hint} and has {priority} explainability importance "
            f"(evidence={len(evidences)}, citations={len(citations)}).{canonical_hint}"
        )

    @staticmethod
    def _element_id(entity: Any) -> str:
        if hasattr(entity, "element_id"):
            return str(entity.element_id)
        return str(entity.id)
