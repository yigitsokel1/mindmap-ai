"""Traversal execution layer for semantic query evidence retrieval."""

from __future__ import annotations

from typing import List, Optional, Sequence

from backend.app.schemas.semantic_query import CandidateEntity, SemanticEvidenceItem
from backend.app.services.query.semantic_query_reader import SemanticQueryReader
from backend.app.services.query.traversal_planner import TraversalPlan


class TraversalExecutor:
    """Executes traversal plans and returns raw evidence subgraphs."""

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
            return raw_items

        filtered: List[SemanticEvidenceItem] = []
        for item in raw_items:
            relation_name = (item.relation_type or "").upper()
            if relation_name in traversal_plan.relation_whitelist:
                filtered.append(item)
        return filtered or raw_items
