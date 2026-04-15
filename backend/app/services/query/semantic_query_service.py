"""Deterministic semantic grounded query service."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.semantic_query import (
    CitationItem,
    RelatedNodeItem,
    SemanticEvidenceItem,
    SemanticQueryAnswer,
    SemanticQueryRequest,
)


logger = logging.getLogger(__name__)


class SemanticQueryServiceError(RuntimeError):
    """Raised when semantic query execution fails internally."""


class SemanticQueryService:
    """Answers semantic questions using graph evidence only."""

    def __init__(self) -> None:
        self.db = Neo4jDatabase()
        if not self.db.driver:
            self.db.connect()

    def answer(self, request: SemanticQueryRequest) -> SemanticQueryAnswer:
        try:
            tokens = self._tokenize_question(request.question)
            logger.info(
                "Semantic query received question_len=%d token_count=%d document_id=%s node_types=%s include_citations=%s max_evidence=%d",
                len(request.question),
                len(tokens),
                request.document_id,
                request.node_types,
                request.include_citations,
                request.max_evidence,
            )
            candidate_nodes = self._find_candidate_nodes(
                tokens=tokens,
                document_id=request.document_id,
                node_types=request.node_types,
            )
            evidence = self._collect_evidence(candidate_nodes, request.max_evidence, request.document_id)
            citations = self._collect_citations(evidence, request.include_citations)
            related_nodes = self._to_related_nodes(candidate_nodes)
            answer_text = self._build_answer_text(request.question, evidence, related_nodes)
            confidence = self._estimate_confidence(len(candidate_nodes), len(evidence))
            logger.info(
                "Semantic query completed candidate_nodes=%d evidence=%d citations=%d confidence=%.2f document_id=%s",
                len(candidate_nodes),
                len(evidence),
                len(citations),
                confidence,
                request.document_id,
            )

            return SemanticQueryAnswer(
                answer=answer_text,
                evidence=evidence,
                related_nodes=related_nodes,
                citations=citations,
                confidence=confidence,
            )
        except Exception as exc:
            logger.error("Semantic query execution failed: %s", exc, exc_info=True)
            raise SemanticQueryServiceError(str(exc)) from exc

    @staticmethod
    def _tokenize_question(question: str) -> List[str]:
        return [part for part in re.findall(r"[a-zA-Z0-9_]+", question.lower()) if len(part) > 2]

    def _find_candidate_nodes(
        self,
        tokens: Sequence[str],
        document_id: Optional[str],
        node_types: Sequence[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
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
        return [record for record in records if record.get("n") is not None]

    def _collect_evidence(
        self, candidate_nodes: Sequence[Dict[str, Any]], max_evidence: int, document_id: Optional[str]
    ) -> List[SemanticEvidenceItem]:
        evidence_items: List[SemanticEvidenceItem] = []
        seen_keys = set()

        for record in candidate_nodes:
            node = record.get("n")
            if node is None:
                continue
            node_id = self._element_id(node)
            query = """
            MATCH (n)-[:OUT_REL]->(ri:RelationInstance)
            WHERE elementId(n) = $node_id
            OPTIONAL MATCH (ev:Evidence)-[:SUPPORTS]->(ri)
            OPTIONAL MATCH (ev)-[:FROM_PASSAGE]->(p:Passage)
            OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(:Section)-[:HAS_PASSAGE]->(p)
            WITH n, ri, ev, p, d
            WHERE (
                $document_id IS NULL
                OR d.uid = $document_id
            )
            OPTIONAL MATCH (p)-[:HAS_INLINE_CITATION]->(ic:InlineCitation)
            OPTIONAL MATCH (ic)-[:REFERS_TO]->(ref:ReferenceEntry)
            RETURN n, ri, ev, p, d, ic, ref
            LIMIT $limit
            """
            records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
                query,
                {"node_id": node_id, "limit": max_evidence, "document_id": document_id},
            )
            for item in records:
                relation_instance = item.get("ri")
                evidence = item.get("ev")
                passage = item.get("p")
                document = item.get("d")
                inline_citation = item.get("ic")
                reference_entry = item.get("ref")

                if relation_instance is None:
                    continue
                if evidence is None and passage is None:
                    continue
                key = (
                    self._element_id(relation_instance),
                    self._element_id(evidence) if evidence is not None else "",
                    self._element_id(passage) if passage is not None else "",
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
                        relation_type=self._pick_relation_type(relation_instance, None),
                        page=page,
                        snippet=snippet,
                        related_node_ids=[
                            node_id,
                            self._element_id(relation_instance),
                        ],
                        document_id=self._pick_document_id(document),
                        document_name=self._pick_document_name(document),
                        citation_label=self._pick_citation_label(inline_citation, reference_entry),
                        reference_entry_id=self._element_id(reference_entry) if reference_entry else None,
                    )
                )
                if len(evidence_items) >= max_evidence:
                    return evidence_items

        return evidence_items

    @staticmethod
    def _collect_citations(
        evidence: Sequence[SemanticEvidenceItem], include_citations: bool
    ) -> List[CitationItem]:
        if not include_citations:
            return []
        citations: List[CitationItem] = []
        seen = set()
        for item in evidence:
            if not item.citation_label and not item.reference_entry_id:
                continue
            key = (item.citation_label or "", item.reference_entry_id or "")
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                CitationItem(
                    label=item.citation_label or "citation",
                    reference_entry_id=item.reference_entry_id,
                    page=item.page,
                    document_name=item.document_name,
                )
            )
        return citations

    def _to_related_nodes(self, candidate_nodes: Sequence[Dict[str, Any]]) -> List[RelatedNodeItem]:
        nodes: List[RelatedNodeItem] = []
        for record in candidate_nodes:
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
            nodes.append(
                RelatedNodeItem(
                    id=self._element_id(node),
                    type=node_type,
                    display_name=str(display_name),
                )
            )
        return nodes

    @staticmethod
    def _build_answer_text(
        question: str, evidence: Sequence[SemanticEvidenceItem], related_nodes: Sequence[RelatedNodeItem]
    ) -> str:
        if not related_nodes:
            logger.info("Semantic query empty result: no candidate nodes for question=%r", question)
            return f"No semantic grounding found for: {question}"
        if not evidence:
            logger.info(
                "Semantic query no-evidence result: matched_nodes=%d question=%r",
                len(related_nodes),
                question,
            )
            return f"Matched semantic nodes for '{question}', but no supporting evidence was found."

        intent = SemanticQueryService._classify_question(question)
        first = evidence[0]
        first_node = related_nodes[0].display_name
        target = related_nodes[1].display_name if len(related_nodes) > 1 else "related context"
        if intent == "evidence":
            if first.snippet:
                return f"Evidence supporting {first_node}: {first.snippet}"
            return f"Evidence exists for {first_node} via relation {first.relation_type}."
        if intent in {"reference", "citation"}:
            cited = [item.citation_label for item in evidence if item.citation_label]
            if cited:
                unique = ", ".join(sorted(dict.fromkeys(cited))[:3])
                return f"Relevant citations for {first_node}: {unique}."
            return f"Reference evidence for {first_node} was found, but no citation labels were available."
        if intent == "method":
            return f"Method-related grounding: {first_node} is linked to {target} via {first.relation_type}."
        if intent == "concept":
            return f"Concept grounding: {first_node} is semantically connected to {target} via {first.relation_type}."
        if first.snippet:
            return f"{first_node} is connected to {target} via {first.relation_type}. Evidence: {first.snippet}"
        return f"{first_node} is connected to {target} via {first.relation_type}."

    @staticmethod
    def _estimate_confidence(candidate_count: int, evidence_count: int) -> float:
        if candidate_count == 0 or evidence_count == 0:
            return 0.0
        raw = min(1.0, 0.25 + (0.1 * min(candidate_count, 4)) + (0.12 * min(evidence_count, 4)))
        return round(raw, 2)

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
    def _pick_relation_type(relation_instance: Any, relation: Any) -> str:
        if relation_instance:
            rel_type = relation_instance.get("type")
            if rel_type:
                return str(rel_type)
        return str(getattr(relation, "type", "RELATED_TO"))

    @staticmethod
    def _classify_question(question: str) -> str:
        lower = question.lower()
        keywords = (
            ("method", ["method", "methods"]),
            ("concept", ["concept", "concepts"]),
            ("evidence", ["evidence", "supports", "supported"]),
            ("reference", ["reference", "references", "cited"]),
            ("citation", ["citation", "citations"]),
        )
        for intent, terms in keywords:
            if any(term in lower for term in terms):
                return intent
        return "general"

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
