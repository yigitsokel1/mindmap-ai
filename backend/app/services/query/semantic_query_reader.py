"""Read-only graph access for semantic query orchestration."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.semantic_query import CandidateEntity, SemanticEvidenceItem
from backend.app.services.normalization.canonical_normalizer import normalize_for_match
from backend.app.services.query.traversal_planner import TraversalPlan


class SemanticQueryReader:
    """Encapsulates query-time Cypher for candidate/evidence lookups."""

    def __init__(self, db: Neo4jDatabase | None = None) -> None:
        self.db = db or Neo4jDatabase()
        if not self.db.driver:
            self.db.connect()

    def find_candidate_entities(
        self,
        tokens: Sequence[str],
        document_id: Optional[str],
        node_types: Sequence[str],
        limit: int = 20,
    ) -> List[CandidateEntity]:
        if not tokens:
            return []

        query = """
        MATCH (n)
        WHERE any(lbl IN labels(n) WHERE lbl IN ['Author', 'Institution', 'Concept', 'Method', 'Dataset', 'Metric', 'Task'])
          AND NOT n:Document
          AND NOT n:Section
          AND NOT n:Passage
          AND NOT n:ReferenceEntry
          AND NOT n:InlineCitation
          AND NOT n:Evidence
          AND NOT n:RelationInstance
          AND (
            $document_id IS NULL
            OR EXISTS {
                MATCH (n)-[:OUT_REL]->(:RelationInstance)<-[:SUPPORTS]-(:Evidence)-[:FROM_PASSAGE]->(:Passage)<-[:HAS_PASSAGE]-(:Section)<-[:HAS_SECTION]-(d:Document {uid: $document_id})
            }
          )
          AND (
            size($node_types) = 0
            OR any(label IN labels(n) WHERE label IN $node_types)
          )
          AND (
            toLower(coalesce(n.canonical_name, "")) CONTAINS $joined_tokens
            OR any(token IN $tokens WHERE
                toLower(coalesce(n.canonical_name, "")) CONTAINS token
                OR toLower(coalesce(n.name, "")) CONTAINS token
                OR toLower(coalesce(n.title, "")) CONTAINS token
            )
          )
        RETURN DISTINCT n
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {
                "tokens": list(tokens),
                "joined_tokens": " ".join(tokens),
                "document_id": document_id,
                "node_types": list(node_types),
                "limit": limit,
            },
        )
        candidates: List[CandidateEntity] = []
        for record in records:
            node = record.get("n")
            if node is None:
                continue
            labels = list(getattr(node, "labels", []))
            node_type = labels[0] if labels else "Node"
            display_name = (
                node.get("display_name")
                or node.get("canonical_name")
                or node.get("name")
                or node.get("title")
                or node.get("id")
                or self._element_id(node)
            )
            candidates.append(
                CandidateEntity(
                    entity_id=self._element_id(node),
                    name=str(display_name),
                    type=node_type,
                    score=1.0,
                    match_reason="token_match",
                    source="local",
                )
            )
        return candidates

    def collect_evidence(
        self,
        candidates: Sequence[CandidateEntity],
        max_evidence: int,
        document_id: Optional[str],
        traversal_plan: TraversalPlan,
    ) -> List[SemanticEvidenceItem]:
        evidence_items: List[SemanticEvidenceItem] = []
        seen_keys = set()
        per_candidate_limit = traversal_plan.max_evidence_per_candidate

        for candidate in candidates:
            one_hop_query = """
            MATCH (n)-[:OUT_REL]->(ri:RelationInstance)
            WHERE elementId(n) = $node_id
            OPTIONAL MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
            OPTIONAL MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
            OPTIONAL MATCH (sec:Section)-[:HAS_PASSAGE]->(p)
            OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p)
            WITH n, ri, ev, p, d, sec
            WHERE (
                $document_id IS NULL
                OR d.uid = $document_id
            )
            OPTIONAL MATCH (p)-[:HAS_INLINE_CITATION]->(ic:InlineCitation)
            OPTIONAL MATCH (ic)-[:REFERS_TO]->(ref:ReferenceEntry)
            RETURN n, ri, ev, p, d, sec, ic, ref
            ORDER BY
                CASE
                    WHEN $prioritize_citations AND (ic IS NOT NULL OR ref IS NOT NULL) THEN 1
                    ELSE 0
                END DESC,
                coalesce(ev.confidence, ri.confidence, 0.0) DESC
            LIMIT $limit
            """
            records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
                one_hop_query,
                {
                    "node_id": candidate.entity_id,
                    "limit": per_candidate_limit,
                    "document_id": document_id,
                    "prioritize_citations": traversal_plan.prioritize_citations,
                },
            )
            if traversal_plan.max_depth >= 2:
                two_hop_query = """
                MATCH (n)-[:OUT_REL]->(ri1:RelationInstance)
                WHERE elementId(n) = $node_id
                OPTIONAL MATCH (ri1)-[:OUT_REL]->(mid)
                OPTIONAL MATCH (mid)-[:OUT_REL]->(ri:RelationInstance)
                OPTIONAL MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
                OPTIONAL MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
                OPTIONAL MATCH (sec:Section)-[:HAS_PASSAGE]->(p)
                OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p)
                WITH ri, ev, p, d, sec
                WHERE ri IS NOT NULL
                  AND ($document_id IS NULL OR d.uid = $document_id)
                OPTIONAL MATCH (p)-[:HAS_INLINE_CITATION]->(ic:InlineCitation)
                OPTIONAL MATCH (ic)-[:REFERS_TO]->(ref:ReferenceEntry)
                RETURN ri, ev, p, d, sec, ic, ref
                ORDER BY
                    CASE
                        WHEN $prioritize_citations AND (ic IS NOT NULL OR ref IS NOT NULL) THEN 1
                        ELSE 0
                    END DESC,
                    coalesce(ev.confidence, ri.confidence, 0.0) DESC
                LIMIT $limit
                """
                two_hop_records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
                    two_hop_query,
                    {
                        "node_id": candidate.entity_id,
                        "limit": per_candidate_limit,
                        "document_id": document_id,
                        "prioritize_citations": traversal_plan.prioritize_citations,
                    },
                )
                records.extend(two_hop_records)
            for item in records:
                relation_instance = item.get("ri")
                evidence = item.get("ev")
                passage = item.get("p")
                document = item.get("d")
                section = item.get("sec")
                inline_citation = item.get("ic")
                reference_entry = item.get("ref")

                if relation_instance is None:
                    continue
                if evidence is None and passage is None:
                    continue
                key = (
                    self._element_id(relation_instance),
                    self._element_id(evidence) if evidence is not None else "",
                    self._canonicalize_snippet(
                        str(passage.get("text", "") if passage is not None else evidence.get("text", "") if evidence is not None else "")
                    ),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                snippet = ""
                page = None
                if passage is not None:
                    snippet = str(passage.get("text", "") or "")[:360]
                    page = self._safe_int(passage.get("page_number"))
                elif evidence is not None:
                    snippet = str(evidence.get("text", "") or evidence.get("statement", ""))[:360]
                    page = self._safe_int(evidence.get("page_number"))

                evidence_items.append(
                    SemanticEvidenceItem(
                        relation_type=self._pick_relation_type(relation_instance),
                        page=page,
                        snippet=snippet,
                        section=self._pick_section_name(section),
                        confidence=self._pick_confidence(relation_instance, evidence),
                        related_node_ids=[candidate.entity_id, self._element_id(relation_instance)],
                        document_id=self._pick_document_id(document),
                        document_name=self._pick_document_name(document),
                        citation_label=self._pick_citation_label(inline_citation, reference_entry),
                        reference_entry_id=self._element_id(reference_entry) if reference_entry else None,
                    )
                )
                if len(evidence_items) >= max_evidence:
                    return evidence_items

        return evidence_items

    def lookup_canonical_candidates(self, tokens: Sequence[str]) -> List[CandidateEntity]:
        """Lookup local entities via CanonicalEntity layer."""
        if not tokens:
            return []
        query = """
        MATCH (e)-[:INSTANCE_OF_CANONICAL]->(c:CanonicalEntity)
        WHERE any(token IN $tokens WHERE
            toLower(coalesce(c.canonical_name, "")) CONTAINS token
            OR token IN coalesce(c.normalized_aliases, [])
            OR token IN coalesce(c.acronyms, [])
        )
        OPTIONAL MATCH (other)-[:INSTANCE_OF_CANONICAL]->(c)
        OPTIONAL MATCH (other)-[:OUT_REL]->(:RelationInstance)<-[:SUPPORTS]-(:Evidence)-[:FROM_PASSAGE]->(:Passage)<-[:HAS_PASSAGE]-(:Section)<-[:HAS_SECTION]-(d:Document)
        WITH e, c, count(DISTINCT d) AS doc_count
        RETURN DISTINCT e, c, doc_count
        ORDER BY doc_count DESC
        LIMIT 20
        """
        normalized_tokens = [normalize_for_match(token) for token in tokens if normalize_for_match(token)]
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {"tokens": normalized_tokens},
        )
        candidates: List[CandidateEntity] = []
        for record in records:
            entity = record.get("e")
            canonical = record.get("c")
            if entity is None or canonical is None:
                continue
            labels = list(getattr(entity, "labels", []))
            node_type = labels[0] if labels else "Node"
            display_name = (
                entity.get("display_name")
                or canonical.get("canonical_name")
                or entity.get("canonical_name")
                or entity.get("name")
                or self._element_id(entity)
            )
            doc_count = int(record.get("doc_count") or 0)
            candidates.append(
                CandidateEntity(
                    entity_id=self._element_id(entity),
                    name=str(display_name),
                    type=node_type,
                    score=max(0.8, min(1.0, 0.8 + (doc_count * 0.02))),
                    match_reason="canonical_linked_match",
                    source="canonical-ready",
                )
            )
        return candidates

    def find_fallback_entities(
        self,
        document_id: Optional[str],
        node_types: Sequence[str],
        intent: str,
        limit: int = 5,
    ) -> List[CandidateEntity]:
        """Fallback selection when token matching yields no candidates."""
        query = """
        MATCH (n)-[:OUT_REL]->(ri:RelationInstance)
        WHERE any(lbl IN labels(n) WHERE lbl IN ['Author', 'Institution', 'Concept', 'Method', 'Dataset', 'Metric', 'Task'])
          AND (
            size($node_types) = 0
            OR any(label IN labels(n) WHERE label IN $node_types)
          )
        OPTIONAL MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
        OPTIONAL MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
        OPTIONAL MATCH (p)-[:HAS_INLINE_CITATION]->(ic:InlineCitation)
        OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p)
        WHERE $document_id IS NULL OR d.uid = $document_id
        WITH n,
             count(DISTINCT ri) AS relation_count,
             count(DISTINCT ev) AS evidence_count,
             count(DISTINCT ic) AS citation_count
        RETURN DISTINCT n, relation_count, evidence_count, citation_count
        ORDER BY
          CASE WHEN $intent = 'CITATION_BASIS' THEN citation_count ELSE evidence_count END DESC,
          relation_count DESC,
          evidence_count DESC,
          citation_count DESC
        LIMIT $limit
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {
                "document_id": document_id,
                "node_types": list(node_types),
                "intent": intent,
                "limit": limit,
            },
        )
        fallback_candidates: List[CandidateEntity] = []
        for record in records:
            node = record.get("n")
            if node is None:
                continue
            labels = list(getattr(node, "labels", []))
            node_type = labels[0] if labels else "Node"
            display_name = (
                node.get("display_name")
                or node.get("canonical_name")
                or node.get("name")
                or node.get("title")
                or node.get("id")
                or self._element_id(node)
            )
            score = float(
                (record.get("relation_count") or 0)
                + (record.get("evidence_count") or 0)
                + (record.get("citation_count") or 0)
            )
            fallback_candidates.append(
                CandidateEntity(
                    entity_id=self._element_id(node),
                    name=str(display_name),
                    type=node_type,
                    score=score,
                    match_reason="graph_density_fallback",
                    source="local",
                )
            )
        return fallback_candidates

    @staticmethod
    def _pick_document_id(document: Any) -> Optional[str]:
        if not document:
            return None
        return str(document.get("uid") or document.get("id") or document.get("name") or "")

    @staticmethod
    def _pick_document_name(document: Any) -> Optional[str]:
        if not document:
            return None
        name = (
            document.get("title")
            or document.get("file_name")
            or document.get("saved_file_name")
            or document.get("name")
        )
        return str(name) if name else None

    @staticmethod
    def _pick_citation_label(inline_citation: Any, reference_entry: Any) -> Optional[str]:
        if inline_citation:
            labels = inline_citation.get("reference_labels") or []
            if labels:
                return str(labels[0])
            keys = inline_citation.get("reference_keys") or []
            if keys:
                return str(keys[0])
            val = inline_citation.get("raw_text")
            if val:
                return str(val)
        if reference_entry:
            val = (
                reference_entry.get("citation_key_numeric")
                or reference_entry.get("citation_key_author_year")
                or reference_entry.get("title_guess")
            )
            if val:
                return str(val)
        return None

    @staticmethod
    def _pick_relation_type(relation_instance: Any) -> str:
        if relation_instance:
            rel_type = relation_instance.get("type")
            if rel_type:
                return str(rel_type)
        return "RELATED_TO"

    @staticmethod
    def _pick_section_name(section: Any) -> Optional[str]:
        if not section:
            return "Unknown"
        title = section.get("title") or section.get("name") or section.get("heading")
        return str(title) if title else "Unknown"

    @staticmethod
    def _pick_confidence(relation_instance: Any, evidence: Any) -> float:
        for source in (relation_instance, evidence):
            if not source:
                continue
            raw = source.get("confidence")
            try:
                if raw is not None:
                    return max(0.0, min(1.0, float(raw)))
            except (TypeError, ValueError):
                continue
        return 0.5

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _element_id(entity: Any) -> str:
        if entity is None:
            return ""
        if hasattr(entity, "element_id"):
            return str(entity.element_id)
        if hasattr(entity, "id"):
            return str(entity.id)
        uid = entity.get("uid") if hasattr(entity, "get") else None
        return str(uid or "")

    @staticmethod
    def _canonicalize_snippet(text: str) -> str:
        return " ".join((text or "").strip().lower().split())
