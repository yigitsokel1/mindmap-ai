"""Traversal planning rules for semantic query execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from backend.app.services.query.question_interpreter import InterpretedQuestion


@dataclass(frozen=True)
class TraversalPlan:
    """Explicit traversal strategy produced from interpreted intent."""

    strategy: str
    relation_directions: List[str]
    prioritize_citations: bool
    max_candidate_nodes: int
    max_evidence_per_candidate: int


class TraversalPlanner:
    """Maps interpreted question intent to deterministic traversal plans."""

    def build_plan(self, interpreted: InterpretedQuestion, max_evidence: int) -> TraversalPlan:
        intent = interpreted.intent
        if intent == "METHOD_USAGE":
            return TraversalPlan(
                strategy="method_centered_scan",
                relation_directions=["outgoing", "incoming"],
                prioritize_citations=False,
                max_candidate_nodes=25,
                max_evidence_per_candidate=max(2, min(max_evidence, 8)),
            )
        if intent == "CITATION_BASIS":
            return TraversalPlan(
                strategy="citation_chain_priority",
                relation_directions=["outgoing"],
                prioritize_citations=True,
                max_candidate_nodes=20,
                max_evidence_per_candidate=max(3, min(max_evidence + 1, 10)),
            )
        if intent == "RELATION_LOOKUP":
            return TraversalPlan(
                strategy="relation_lookup_scan",
                relation_directions=["outgoing", "incoming"],
                prioritize_citations=False,
                max_candidate_nodes=20,
                max_evidence_per_candidate=max(2, min(max_evidence, 7)),
            )
        if intent == "PROBLEM":
            return TraversalPlan(
                strategy="problem_context_scan",
                relation_directions=["outgoing"],
                prioritize_citations=False,
                max_candidate_nodes=18,
                max_evidence_per_candidate=max(2, min(max_evidence, 6)),
            )
        return TraversalPlan(
            strategy="broad_summary_sweep",
            relation_directions=["outgoing"],
            prioritize_citations=False,
            max_candidate_nodes=18,
            max_evidence_per_candidate=max(2, min(max_evidence, 6)),
        )
