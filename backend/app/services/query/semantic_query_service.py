"""Deterministic semantic grounded query service."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.semantic_query import (
    CitationItem,
    MatchedEntityItem,
    QueryExplanation,
    RelatedNodeItem,
    SemanticEvidenceItem,
    SemanticQueryAnswer,
    SemanticQueryRequest,
)
from backend.app.services.query.evidence_ranker import EvidenceRanker
from backend.app.services.query.question_interpreter import InterpretedQuestion, QuestionInterpreter
from backend.app.services.query.traversal_planner import TraversalPlan, TraversalPlanner


logger = logging.getLogger(__name__)


class SemanticQueryServiceError(RuntimeError):
    """Raised when semantic query execution fails internally."""


class SemanticQueryService:
    """Answers semantic questions using graph evidence only."""

    def __init__(self) -> None:
        self.db = Neo4jDatabase()
        if not self.db.driver:
            self.db.connect()
        self.interpreter = QuestionInterpreter()
        self.traversal_planner = TraversalPlanner()
        self.evidence_ranker = EvidenceRanker()

    def answer(self, request: SemanticQueryRequest) -> SemanticQueryAnswer:
        try:
            interpreted = self.interpret_question(request)
            logger.info(
                "Semantic query received question_len=%d intent=%s document_id=%s node_types=%s include_citations=%s max_evidence=%d",
                len(request.question),
                interpreted.intent,
                request.document_id,
                request.node_types,
                request.include_citations,
                request.max_evidence,
            )
            candidate_nodes = self.select_candidate_entities(request, interpreted)
            traversal_plan = self.decide_traversal_scope(request, interpreted)
            evidence = self.collect_evidence(request, candidate_nodes, traversal_plan)
            ranked_evidence = self.rank_evidence(interpreted, candidate_nodes, evidence, request.max_evidence)
            citations = self._collect_citations(ranked_evidence, request.include_citations)
            related_nodes = self._to_related_nodes(candidate_nodes)
            answer_text = self.compose_answer(request, interpreted, ranked_evidence, related_nodes)
            confidence = self._estimate_confidence(len(candidate_nodes), len(ranked_evidence))
            explanation = self._build_explanation(interpreted, candidate_nodes, ranked_evidence, traversal_plan)
            logger.info(
                "Semantic query completed candidate_nodes=%d evidence=%d citations=%d confidence=%.2f document_id=%s",
                len(candidate_nodes),
                len(ranked_evidence),
                len(citations),
                confidence,
                request.document_id,
            )

            return SemanticQueryAnswer(
                answer=answer_text,
                query_intent=interpreted.intent,
                matched_entities=self._to_matched_entities(candidate_nodes),
                evidence=ranked_evidence,
                related_nodes=related_nodes,
                citations=citations,
                explanation=explanation,
                confidence=confidence,
            )
        except Exception as exc:
            logger.error("Semantic query execution failed: %s", exc, exc_info=True)
            raise SemanticQueryServiceError(str(exc)) from exc

    @staticmethod
    def _tokenize_question(question: str) -> List[str]:
        return [part for part in re.findall(r"[a-zA-Z0-9_]+", question.lower()) if len(part) > 2]

    def interpret_question(self, request: SemanticQueryRequest) -> InterpretedQuestion:
        return self.interpreter.interpret(request.question, request.document_id)

    def select_candidate_entities(
        self, request: SemanticQueryRequest, interpreted: InterpretedQuestion
    ) -> List[Dict[str, Any]]:
        tokens = interpreted.entity_hints or self._tokenize_question(request.question)
        return self._find_candidate_nodes(
            tokens=tokens,
            document_id=request.document_id,
            node_types=request.node_types,
        )

    def decide_traversal_scope(
        self, request: SemanticQueryRequest, interpreted: InterpretedQuestion
    ) -> TraversalPlan:
        return self.traversal_planner.build_plan(interpreted, request.max_evidence)

    def collect_evidence(
        self,
        request: SemanticQueryRequest,
        candidate_nodes: Sequence[Dict[str, Any]],
        traversal_plan: TraversalPlan,
    ) -> List[SemanticEvidenceItem]:
        return self._collect_evidence(
            candidate_nodes=candidate_nodes,
            max_evidence=request.max_evidence,
            document_id=request.document_id,
            traversal_plan=traversal_plan,
        )

    def rank_evidence(
        self,
        interpreted: InterpretedQuestion,
        candidate_nodes: Sequence[Dict[str, Any]],
        evidence: Sequence[SemanticEvidenceItem],
        max_evidence: int,
    ) -> List[SemanticEvidenceItem]:
        candidate_names = []
        for node in self._to_related_nodes(candidate_nodes):
            candidate_names.append(node.display_name)
        ranked = self.evidence_ranker.rank(evidence, interpreted=interpreted, candidate_names=candidate_names)
        return ranked[:max_evidence]

    def compose_answer(
        self,
        request: SemanticQueryRequest,
        interpreted: InterpretedQuestion,
        evidence: Sequence[SemanticEvidenceItem],
        related_nodes: Sequence[RelatedNodeItem],
    ) -> str:
        return self._build_answer_text(request.question, interpreted.intent, evidence, related_nodes)

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
        self,
        candidate_nodes: Sequence[Dict[str, Any]],
        max_evidence: int,
        document_id: Optional[str],
        traversal_plan: TraversalPlan,
    ) -> List[SemanticEvidenceItem]:
        evidence_items: List[SemanticEvidenceItem] = []
        seen_keys = set()
        per_candidate_limit = traversal_plan.max_evidence_per_candidate

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
            OPTIONAL MATCH (sec:Section)-[:HAS_PASSAGE]->(p)
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
                {"node_id": node_id, "limit": per_candidate_limit, "document_id": document_id},
            )
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
                        section=self._pick_section_name(section),
                        confidence=self._pick_confidence(relation_instance, evidence),
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
        question: str,
        query_intent: str,
        evidence: Sequence[SemanticEvidenceItem],
        related_nodes: Sequence[RelatedNodeItem],
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

        top_evidence = SemanticQueryService._dedupe_evidence(evidence, limit=3)
        first = top_evidence[0]
        first_node = related_nodes[0].display_name
        concepts = ", ".join(node.display_name for node in related_nodes[:3])
        rel_types = ", ".join(sorted({item.relation_type for item in top_evidence if item.relation_type}))
        snippets = [item.snippet.strip() for item in top_evidence if item.snippet.strip()]
        supported_fact = snippets[0] if snippets else ""
        section_list = ", ".join(sorted({(item.section or "Unknown") for item in top_evidence})[:3])

        if query_intent == "SUMMARY":
            if supported_fact:
                return f"{first_node} and related concepts ({concepts}) are grounded by evidence from sections {section_list}. Core evidence: {supported_fact}"
            return f"{first_node} is grounded through relations ({rel_types}) with related concepts: {concepts}."

        if query_intent == "METHOD_USAGE":
            usage_target = related_nodes[1].display_name if len(related_nodes) > 1 else "its linked context"
            if supported_fact:
                return f"Method usage is evidenced as {first_node} connects to {usage_target} through {first.relation_type}. Evidence: {supported_fact}"
            return f"Method usage grounding shows {first_node} linked to {usage_target} through {first.relation_type}."

        if query_intent == "PROBLEM":
            if supported_fact:
                return f"The problem framing centers on {first_node}. Supporting passage: {supported_fact}"
            return f"The problem framing is grounded around {first_node} with relation pattern {rel_types or first.relation_type}."

        if query_intent == "CITATION_BASIS":
            cited = [item.citation_label for item in top_evidence if item.citation_label]
            unique = ", ".join(sorted(dict.fromkeys(cited))[:4])
            if unique:
                return f"This answer is based on citation-backed evidence for {first_node}: {unique}."
            if supported_fact:
                return f"Reference-grounded evidence for {first_node} was found: {supported_fact}"
            return f"Reference evidence exists for {first_node}, but explicit citation labels were not available."

        if query_intent == "RELATION_LOOKUP":
            if supported_fact:
                return f"Relation lookup shows {first_node} connected via {rel_types or first.relation_type}. Evidence: {supported_fact}"
            return f"Relation lookup found {first_node} connected through {rel_types or first.relation_type}."

        if supported_fact:
            return f"{first_node} is grounded via {first.relation_type}. Evidence: {supported_fact}"
        return f"{first_node} is connected through {first.relation_type}."

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

    def _to_matched_entities(self, candidate_nodes: Sequence[Dict[str, Any]]) -> List[MatchedEntityItem]:
        entities: List[MatchedEntityItem] = []
        for node in self._to_related_nodes(candidate_nodes):
            entities.append(MatchedEntityItem(id=node.id, type=node.type, display_name=node.display_name))
        return entities

    def _build_explanation(
        self,
        interpreted: InterpretedQuestion,
        candidate_nodes: Sequence[Dict[str, Any]],
        evidence: Sequence[SemanticEvidenceItem],
        traversal_plan: TraversalPlan,
    ) -> QueryExplanation:
        entity_reasons = []
        if interpreted.entity_hints:
            entity_reasons.append(f"Selected entities using query hints: {', '.join(interpreted.entity_hints[:4])}.")
        entity_reasons.append(
            f"Candidate selection returned {len(candidate_nodes)} graph entities for intent {interpreted.intent}."
        )
        evidence_reasons = [
            f"Traversal strategy '{traversal_plan.strategy}' prioritized {', '.join(traversal_plan.relation_directions)} links."
        ]
        top_evidence = self._dedupe_evidence(evidence, limit=5)
        if evidence:
            evidence_reasons.append(
                f"Top evidence prioritized by entity mention, section weight, citation presence, confidence, and relation match."
            )
        reasoning_path = [
            f"question_intent:{interpreted.intent}",
            f"candidate_entities:{len(candidate_nodes)}",
            f"evidence_candidates:{len(evidence)}",
            f"selected_top_evidence:{len(top_evidence)}",
            f"strategy:{traversal_plan.strategy}",
        ]
        selected_sections = sorted(
            {
                (item.section or "Unknown")
                for item in top_evidence
                if (item.section or "Unknown").strip()
            }
        )
        selection_signals = [
            "entity_mention_match",
            "intent_section_priority",
            "citation_signal_weighted_by_intent",
            "relation_type_alignment",
            "confidence_weight",
            "duplicate_passage_penalty",
            "duplicate_document_penalty",
            "diversity_bonus",
        ]
        return QueryExplanation(
            why_these_entities=entity_reasons,
            why_this_evidence=evidence_reasons,
            reasoning_path=reasoning_path,
            selected_sections=selected_sections,
            selection_signals=selection_signals,
        )

    @staticmethod
    def _dedupe_evidence(
        evidence: Sequence[SemanticEvidenceItem], limit: int
    ) -> List[SemanticEvidenceItem]:
        deduped: List[SemanticEvidenceItem] = []
        seen = set()
        for item in evidence:
            key = " ".join((item.snippet or "").strip().lower().split())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

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
