"""Deterministic semantic grounded query service."""

from __future__ import annotations

import logging
from typing import List, Sequence

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.semantic_query import (
    CandidateEntity,
    CitationItem,
    SemanticEvidenceItem,
    SemanticQueryAnswer,
    SemanticQueryRequest,
)
from backend.app.services.query.answer_composer import AnswerComposer
from backend.app.services.query.candidate_selector import CandidateSelector
from backend.app.services.query.evidence_ranker import EvidenceRanker
from backend.app.services.query.explanation_builder import ExplanationBuilder
from backend.app.services.query.question_interpreter import InterpretedQuestion, QuestionInterpreter
from backend.app.services.query.semantic_query_reader import SemanticQueryReader
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
        self.reader = SemanticQueryReader(self.db)
        self.candidate_selector = CandidateSelector(self.reader)
        self.answer_composer = AnswerComposer()
        self.explanation_builder = ExplanationBuilder()

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
            candidate_entities = self.candidate_selector.select_candidates(
                question=request.question,
                interpreted=interpreted,
                document_id=request.document_id,
                node_types=request.node_types,
            )
            traversal_plan = self.decide_traversal_scope(request, interpreted)
            evidence = self.reader.collect_evidence(
                candidates=candidate_entities,
                max_evidence=request.max_evidence,
                document_id=request.document_id,
                traversal_plan=traversal_plan,
            )
            ranked_evidence = self.rank_evidence(
                interpreted,
                candidate_entities,
                evidence,
                request.max_evidence,
            )
            citations = self._collect_citations(ranked_evidence, request.include_citations)
            related_nodes = self.candidate_selector.to_related_nodes(candidate_entities)
            answer_text = self.answer_composer.compose(
                question=request.question,
                query_intent=interpreted.intent,
                evidence=ranked_evidence,
                candidates=candidate_entities,
            )
            confidence = self._estimate_confidence(len(candidate_entities), len(ranked_evidence))
            answer_text, limited_evidence, uncertainty_signal, uncertainty_reason = self.answer_composer.apply_guardrails(
                answer_text=answer_text,
                query_intent=interpreted.intent,
                evidence=ranked_evidence,
                citations=citations,
                confidence=confidence,
            )
            explanation = self.explanation_builder.build(
                interpreted=interpreted,
                candidates=candidate_entities,
                evidence=ranked_evidence,
                traversal_plan=traversal_plan,
            )
            explanation.reasoning_path.append(f"limited_evidence:{limited_evidence}")
            explanation.reasoning_path.append(f"uncertainty_signal:{uncertainty_signal}")
            logger.info(
                "Semantic query completed candidate_nodes=%d evidence=%d citations=%d confidence=%.2f document_id=%s",
                len(candidate_entities),
                len(ranked_evidence),
                len(citations),
                confidence,
                request.document_id,
            )

            return SemanticQueryAnswer(
                answer=answer_text,
                query_intent=interpreted.intent,
                matched_entities=self.candidate_selector.to_matched_entities(candidate_entities),
                evidence=ranked_evidence,
                related_nodes=related_nodes,
                citations=citations,
                explanation=explanation,
                confidence=confidence,
                limited_evidence=limited_evidence,
                uncertainty_signal=uncertainty_signal,
                uncertainty_reason=uncertainty_reason,
            )
        except Exception as exc:
            logger.error("Semantic query execution failed: %s", exc, exc_info=True)
            raise SemanticQueryServiceError(str(exc)) from exc

    def interpret_question(self, request: SemanticQueryRequest) -> InterpretedQuestion:
        return self.interpreter.interpret(request.question, request.document_id)

    def decide_traversal_scope(
        self, request: SemanticQueryRequest, interpreted: InterpretedQuestion
    ) -> TraversalPlan:
        return self.traversal_planner.build_plan(interpreted, request.max_evidence)

    def rank_evidence(
        self,
        interpreted: InterpretedQuestion,
        candidate_entities: Sequence[CandidateEntity],
        evidence: Sequence[SemanticEvidenceItem],
        max_evidence: int,
    ) -> List[SemanticEvidenceItem]:
        candidate_names = [candidate.name for candidate in candidate_entities]
        ranked = self.evidence_ranker.rank(evidence, interpreted=interpreted, candidate_names=candidate_names)
        return ranked[:max_evidence]

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


    @staticmethod
    def _estimate_confidence(candidate_count: int, evidence_count: int) -> float:
        if candidate_count == 0 or evidence_count == 0:
            return 0.0
        raw = min(1.0, 0.25 + (0.1 * min(candidate_count, 4)) + (0.12 * min(evidence_count, 4)))
        return round(raw, 2)

