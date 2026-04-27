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
from backend.app.services.query.evidence_clusterer import EvidenceClusterer
from backend.app.services.query.explanation_builder import ExplanationBuilder
from backend.app.services.query.insight_builder import InsightBuilder
from backend.app.services.query.question_interpreter import InterpretedQuestion, QuestionInterpreter
from backend.app.services.query.semantic_query_reader import SemanticQueryReader
from backend.app.services.query.traversal_executor import TraversalExecutor
from backend.app.services.query.traversal_planner import TraversalPlan, TraversalPlanner


logger = logging.getLogger(__name__)


class SemanticQueryServiceError(RuntimeError):
    """Raised when semantic query execution fails internally."""

    def __init__(self, message: str, category: str = "internal_error") -> None:
        super().__init__(message)
        self.category = category


class SemanticQueryService:
    """Answers semantic questions using graph evidence only."""

    def __init__(self) -> None:
        self.db = Neo4jDatabase()
        if not self.db.driver:
            self.db.connect()
        self.interpreter = QuestionInterpreter()
        self.traversal_planner = TraversalPlanner()
        self.evidence_ranker = EvidenceRanker()
        self.evidence_clusterer = EvidenceClusterer()
        self.insight_builder = InsightBuilder()
        self.reader = SemanticQueryReader(self.db)
        self.traversal_executor = TraversalExecutor()
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
            if not candidate_entities:
                return self._build_abstain_response(
                    request=request,
                    interpreted=interpreted,
                    reasons=[f'No direct match for "{request.question}".', "No supporting passages found."],
                    closest_concepts=[],
                )
            traversal_plan = self.decide_traversal_scope(request, interpreted)
            evidence = self.traversal_executor.execute(
                reader=self.reader,
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
            clusters = self.evidence_clusterer.build_clusters(ranked_evidence, candidate_entities)
            insights = self.insight_builder.build(clusters)
            if clusters:
                clustered_evidence = [evidence_item for cluster in clusters for evidence_item in cluster.evidences]
                ranked_evidence = self.answer_composer.order_evidence(clustered_evidence, clusters)
            else:
                ranked_evidence = self.answer_composer.order_evidence(ranked_evidence, clusters)
            key_points = self.answer_composer.compose_key_points(interpreted.intent, clusters, insights)
            citations = self._collect_citations(ranked_evidence, request.include_citations)
            related_nodes = self.candidate_selector.to_related_nodes(candidate_entities)
            focus_seed_ids = self._build_focus_seed_ids(related_nodes=related_nodes, evidence=ranked_evidence)
            primary_focus_node_id, secondary_focus_node_ids = self._split_focus_layers(focus_seed_ids)
            closest_concepts = [candidate.name for candidate in candidate_entities[:3]]
            if len(ranked_evidence) == 0 and request.answer_mode == "answer":
                reasons = [
                    f'No direct match for "{request.question}".' if not candidate_entities else "No supporting passages found.",
                    "No supporting passages found.",
                ]
                return self._build_abstain_response(
                    request=request,
                    interpreted=interpreted,
                    reasons=reasons,
                    closest_concepts=closest_concepts,
                    matched_entities=self.candidate_selector.to_matched_entities(candidate_entities),
                    related_nodes=related_nodes,
                    focus_seed_ids=focus_seed_ids,
                    primary_focus_node_id=primary_focus_node_id,
                    secondary_focus_node_ids=secondary_focus_node_ids,
                    citations=citations,
                )
            answer_text = self.answer_composer.compose(
                question=request.question,
                query_intent=interpreted.intent,
                evidence=ranked_evidence,
                candidates=candidate_entities,
            )
            confidence, confidence_badge = self._estimate_grounded_confidence(
                evidence_count=len(ranked_evidence),
                citation_count=len(citations),
                cluster_importance=[cluster.importance for cluster in clusters],
            )
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
                primary_focus_node_id=primary_focus_node_id,
                secondary_focus_node_ids=secondary_focus_node_ids,
                focus_seed_ids=focus_seed_ids,
                citations=citations,
                explanation=explanation,
                key_points=key_points,
                insights=insights,
                clusters=clusters,
                confidence=confidence,
                confidence_badge=confidence_badge,
                limited_evidence=limited_evidence,
                uncertainty_signal=uncertainty_signal,
                uncertainty_reason=uncertainty_reason,
                no_answer_reasons=[],
                closest_concepts=closest_concepts,
            )
        except ValueError as exc:
            logger.error("Semantic query validation failed: %s", exc, exc_info=True)
            raise SemanticQueryServiceError(str(exc), category="validation_error") from exc
        except Exception as exc:
            logger.error("Semantic query execution failed: %s", exc, exc_info=True)
            message = str(exc).lower()
            if "not found" in message:
                category = "not_found"
            elif "timeout" in message:
                category = "dependency_error"
            else:
                category = "dependency_error"
            raise SemanticQueryServiceError(str(exc), category=category) from exc

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
    def _estimate_grounded_confidence(
        evidence_count: int,
        citation_count: int,
        cluster_importance: Sequence[float],
    ) -> tuple[float, str]:
        if evidence_count == 0:
            return 0.0, "NO_GROUNDING"
        avg_cluster = (sum(cluster_importance) / len(cluster_importance)) if cluster_importance else 0.0
        citation_factor = min(1.0, citation_count / max(1, evidence_count))
        evidence_factor = min(1.0, evidence_count / 5)
        score = round(min(1.0, (0.45 * evidence_factor) + (0.35 * avg_cluster) + (0.20 * citation_factor)), 2)
        if score >= 0.65:
            return score, "GROUNDED"
        if score >= 0.3:
            return score, "WEAK_GROUNDING"
        return score, "NO_GROUNDING"

    def _build_abstain_response(
        self,
        request: SemanticQueryRequest,
        interpreted: InterpretedQuestion,
        reasons: List[str],
        closest_concepts: List[str],
        matched_entities: Sequence = (),
        related_nodes: Sequence = (),
        focus_seed_ids: Sequence[str] = (),
        primary_focus_node_id: str | None = None,
        secondary_focus_node_ids: Sequence[str] = (),
        citations: Sequence = (),
    ) -> SemanticQueryAnswer:
        explanation = self.explanation_builder.build(
            interpreted=interpreted,
            candidates=[],
            evidence=[],
            traversal_plan=self.decide_traversal_scope(request, interpreted),
        )
        explanation.reasoning_path.append("hard_gate:no_grounded_answer")
        return SemanticQueryAnswer(
            answer="No grounded answer found in the current documents.",
            query_intent=interpreted.intent,
            matched_entities=list(matched_entities),
            evidence=[],
            related_nodes=list(related_nodes),
            primary_focus_node_id=primary_focus_node_id,
            secondary_focus_node_ids=list(secondary_focus_node_ids),
            focus_seed_ids=list(focus_seed_ids),
            citations=list(citations),
            explanation=explanation,
            key_points=[],
            insights=[],
            clusters=[],
            confidence=0.0,
            confidence_badge="NO_GROUNDING",
            limited_evidence=True,
            uncertainty_signal=True,
            uncertainty_reason="no_evidence_hard_gate",
            no_answer_reasons=reasons,
            closest_concepts=closest_concepts,
        )

    @staticmethod
    def _build_focus_seed_ids(
        related_nodes: Sequence, evidence: Sequence[SemanticEvidenceItem]
    ) -> List[str]:
        seen: set[str] = set()
        seeds: List[str] = []

        for node in related_nodes:
            node_id = getattr(node, "id", None)
            if isinstance(node_id, str) and node_id and node_id not in seen:
                seen.add(node_id)
                seeds.append(node_id)

        for item in evidence:
            for related_id in item.related_node_ids:
                if related_id and related_id not in seen:
                    seen.add(related_id)
                    seeds.append(related_id)
            if item.reference_entry_id and item.reference_entry_id not in seen:
                seen.add(item.reference_entry_id)
                seeds.append(item.reference_entry_id)

        return seeds

    @staticmethod
    def _split_focus_layers(focus_seed_ids: Sequence[str]) -> tuple[str | None, List[str]]:
        if not focus_seed_ids:
            return None, []
        primary = focus_seed_ids[0]
        secondary = [node_id for node_id in focus_seed_ids[1:] if node_id != primary]
        return primary, secondary

