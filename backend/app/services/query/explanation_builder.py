"""Builds semantic query explanations from orchestration context."""

from __future__ import annotations

from typing import Sequence

from backend.app.schemas.semantic_query import CandidateEntity, QueryExplanation, SemanticEvidenceItem
from backend.app.services.query.answer_composer import AnswerComposer
from backend.app.services.query.question_interpreter import InterpretedQuestion
from backend.app.services.query.traversal_planner import TraversalPlan


class ExplanationBuilder:
    """Assembles explanation payload and reasoning path."""

    def build(
        self,
        interpreted: InterpretedQuestion,
        candidates: Sequence[CandidateEntity],
        evidence: Sequence[SemanticEvidenceItem],
        traversal_plan: TraversalPlan,
    ) -> QueryExplanation:
        entity_reasons = []
        if interpreted.entity_hints:
            entity_reasons.append(
                f"Selected entities using query hints: {', '.join(interpreted.entity_hints[:4])}."
            )
        entity_reasons.append(
            f"Candidate selection returned {len(candidates)} graph entities for intent {interpreted.intent}."
        )
        evidence_reasons = [
            f"Traversal strategy '{traversal_plan.strategy}' prioritized {', '.join(traversal_plan.relation_directions)} links."
        ]
        top_evidence = AnswerComposer.dedupe_evidence(evidence, limit=5)
        if evidence:
            evidence_reasons.append(
                "Evidence ranking prioritized entity mention, section weight, citation presence, confidence, and relation match."
            )
        reasoning_path = [
            f"question_intent:{interpreted.intent}",
            f"candidate_entities:{len(candidates)}",
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
