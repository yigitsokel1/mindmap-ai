"""Traversal execution layer for semantic query evidence retrieval."""

from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Sequence

from backend.app.schemas.semantic_query import CandidateEntity, SemanticEvidenceItem
from backend.app.services.query.semantic_query_reader import SemanticQueryReader
from backend.app.services.query.traversal_planner import TraversalPlan


class TraversalExecutor:
    """Executes traversal plans and returns raw evidence subgraphs."""

    MAX_WEAK_PATHS_PER_RELATION = 2
    WEAK_CONFIDENCE_THRESHOLD = 0.55

    def execute(
        self,
        *,
        reader: SemanticQueryReader,
        candidates: Sequence[CandidateEntity],
        max_evidence: int,
        document_id: Optional[str],
        traversal_plan: TraversalPlan,
    ) -> List[SemanticEvidenceItem]:
        raw_items = reader.collect_evidence(
            candidates=candidates,
            max_evidence=max_evidence,
            document_id=document_id,
            traversal_plan=traversal_plan,
        )
        if not traversal_plan.relation_whitelist:
            return self._suppress_repeated_weak_paths(raw_items)

        filtered = self._filter_relevant_relations(raw_items, traversal_plan.relation_whitelist)
        if not filtered:
            # Keep a small, stable fallback slice to avoid empty answers on sparse ontologies.
            fallback = sorted(raw_items, key=lambda item: float(item.confidence or 0.0), reverse=True)[:2]
            return self._suppress_repeated_weak_paths(fallback)
        return self._suppress_repeated_weak_paths(filtered)

    def _filter_relevant_relations(
        self,
        items: Sequence[SemanticEvidenceItem],
        relation_whitelist: Sequence[str],
    ) -> List[SemanticEvidenceItem]:
        allowed = {relation.upper() for relation in relation_whitelist}
        filtered: List[SemanticEvidenceItem] = []
        for item in items:
            relation_name = (item.relation_type or "").upper()
            if relation_name in allowed:
                filtered.append(item)
        return filtered

    def _suppress_repeated_weak_paths(self, items: Sequence[SemanticEvidenceItem]) -> List[SemanticEvidenceItem]:
        if not items:
            return []
        kept: List[SemanticEvidenceItem] = []
        weak_counts_by_relation: dict[str, int] = defaultdict(int)
        for item in items:
            relation_name = (item.relation_type or "RELATED_TO").upper()
            confidence = float(item.confidence or 0.0)
            if confidence < self.WEAK_CONFIDENCE_THRESHOLD:
                weak_counts_by_relation[relation_name] += 1
                if weak_counts_by_relation[relation_name] > self.MAX_WEAK_PATHS_PER_RELATION:
                    continue
            kept.append(item)
        return kept
