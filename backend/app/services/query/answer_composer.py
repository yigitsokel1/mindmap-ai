"""Answer shaping and guardrail helpers for semantic query responses."""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from backend.app.schemas.semantic_query import (
    CandidateEntity,
    CitationItem,
    EvidenceClusterItem,
    InsightItem,
    SemanticEvidenceItem,
)

logger = logging.getLogger(__name__)


class AnswerComposer:
    """Builds response text and applies uncertainty guardrails."""

    def compose(
        self,
        question: str,
        query_intent: str,
        evidence: Sequence[SemanticEvidenceItem],
        candidates: Sequence[CandidateEntity],
    ) -> str:
        if not candidates:
            logger.info("Semantic query empty result: no candidate nodes for question=%r", question)
            return f"No semantic grounding found for: {question}"
        if not evidence:
            logger.info(
                "Semantic query no-evidence result: matched_nodes=%d question=%r",
                len(candidates),
                question,
            )
            return "We couldn’t find strong supporting evidence for this question in your documents."

        top_evidence = self._dedupe_evidence(evidence, limit=3)
        first = top_evidence[0]
        first_node = candidates[0].name
        concepts = ", ".join(candidate.name for candidate in candidates[:3])
        rel_types = ", ".join(sorted({item.relation_type for item in top_evidence if item.relation_type}))
        snippets = [item.snippet.strip() for item in top_evidence if item.snippet.strip()]
        supported_fact = snippets[0] if snippets else ""
        section_list = ", ".join(sorted({(item.section or "Unknown") for item in top_evidence})[:3])

        if query_intent == "SUMMARY":
            if supported_fact:
                return f"{first_node} and related concepts ({concepts}) are grounded by evidence from sections {section_list}. Core evidence: {supported_fact}"
            return f"{first_node} is grounded through relations ({rel_types}) with related concepts: {concepts}."
        if query_intent == "METHOD_USAGE":
            usage_target = candidates[1].name if len(candidates) > 1 else "its linked context"
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

    def compose_key_points(
        self,
        query_intent: str,
        clusters: Sequence[EvidenceClusterItem],
        insights: Sequence[InsightItem],
    ) -> List[str]:
        points: List[str] = []
        if clusters:
            top_cluster = clusters[0]
            points.append(
                f"Primary cluster: {top_cluster.entity} - {top_cluster.relation_type} ({top_cluster.canonical_frequency} supports)."
            )
        if insights:
            points.append(f"Top insight: {insights[0].text}")
        if query_intent == "RELATION_LOOKUP":
            points.append("Relations are grouped by canonical entity and relation type.")
        elif query_intent == "METHOD_USAGE":
            points.append("Usage patterns prioritize repeated evidence and citation-backed clusters.")
        elif query_intent == "SUMMARY":
            points.append("Summary is grounded by the highest-importance evidence clusters.")
        return points[:3]

    @staticmethod
    def order_evidence(
        evidence: Sequence[SemanticEvidenceItem],
        clusters: Sequence[EvidenceClusterItem],
    ) -> List[SemanticEvidenceItem]:
        cluster_score = {cluster.cluster_key: (cluster.importance, cluster.citation_count) for cluster in clusters}
        ordered = sorted(
            evidence,
            key=lambda item: (
                cluster_score.get(item.cluster_key or "", (0.0, 0))[0],
                cluster_score.get(item.cluster_key or "", (0.0, 0))[1],
                item.confidence or 0.0,
            ),
            reverse=True,
        )
        return ordered

    @staticmethod
    def apply_guardrails(
        answer_text: str,
        query_intent: str,
        evidence: Sequence[SemanticEvidenceItem],
        citations: Sequence[CitationItem],
        confidence: float,
    ) -> tuple[str, bool, bool, Optional[str]]:
        limited_evidence = False
        uncertainty_signal = False
        uncertainty_reason: Optional[str] = None
        guarded_answer = answer_text

        if not evidence:
            limited_evidence = True
            uncertainty_signal = True
            uncertainty_reason = "no_evidence"
            if "limited evidence" not in guarded_answer.lower():
                guarded_answer = f"{guarded_answer} Limited evidence is available for this answer."
            return guarded_answer, limited_evidence, uncertainty_signal, uncertainty_reason

        if query_intent == "CITATION_BASIS" and not citations:
            limited_evidence = True
            uncertainty_signal = True
            uncertainty_reason = "citation_missing"
            guarded_answer = (
                f"{guarded_answer} Citation basis could not be verified because no citation links were found."
            )
            return guarded_answer, limited_evidence, uncertainty_signal, uncertainty_reason

        weak_match = len(evidence) < 2 or confidence < 0.45
        if weak_match:
            limited_evidence = True
            uncertainty_signal = True
            uncertainty_reason = "weak_match"
            if "limited evidence" not in guarded_answer.lower():
                guarded_answer = f"{guarded_answer} This answer is based on limited evidence."
        return guarded_answer, limited_evidence, uncertainty_signal, uncertainty_reason

    @staticmethod
    def dedupe_evidence(
        evidence: Sequence[SemanticEvidenceItem],
        limit: int,
    ) -> list[SemanticEvidenceItem]:
        return AnswerComposer._dedupe_evidence(evidence, limit)

    @staticmethod
    def _dedupe_evidence(
        evidence: Sequence[SemanticEvidenceItem],
        limit: int,
    ) -> list[SemanticEvidenceItem]:
        deduped: list[SemanticEvidenceItem] = []
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
