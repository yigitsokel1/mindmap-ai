"""Candidate selection helpers for semantic query orchestration."""

from __future__ import annotations

import re
from typing import List

from backend.app.schemas.semantic_query import CandidateEntity, MatchedEntityItem, RelatedNodeItem
from backend.app.services.normalization.canonical_normalizer import normalize_for_match
from backend.app.services.query.question_interpreter import InterpretedQuestion
from backend.app.services.query.semantic_query_reader import SemanticQueryReader


class CandidateSelector:
    """Selects candidate entities and maps them to response DTOs."""

    def __init__(self, reader: SemanticQueryReader) -> None:
        self.reader = reader

    @staticmethod
    def tokenize_question(question: str) -> List[str]:
        return [part for part in re.findall(r"[a-zA-Z0-9_]+", question.lower()) if len(part) > 2]

    def select_candidates(
        self,
        question: str,
        interpreted: InterpretedQuestion,
        document_id: str | None,
        node_types: list[str],
    ) -> List[CandidateEntity]:
        tokens = interpreted.entity_hints or self.tokenize_question(question)
        local_candidates = self.reader.find_candidate_entities(
            tokens=tokens,
            document_id=document_id,
            node_types=node_types,
        )
        if not local_candidates:
            local_candidates = self.reader.find_fallback_entities(
                document_id=document_id,
                node_types=node_types,
                intent=interpreted.intent,
            )
        canonical_candidates = self.reader.lookup_canonical_candidates(tokens)
        merged_by_id: dict[str, CandidateEntity] = {}
        for candidate in [*local_candidates, *canonical_candidates]:
            existing = merged_by_id.get(candidate.entity_id)
            if existing is None:
                merged_by_id[candidate.entity_id] = candidate
                continue
            if candidate.score > existing.score:
                merged_by_id[candidate.entity_id] = candidate
                continue
            if candidate.source == "canonical-ready" and existing.source != "canonical-ready":
                merged_by_id[candidate.entity_id] = candidate
        canonical_clusters: dict[str, CandidateEntity] = {}
        for item in sorted(merged_by_id.values(), key=lambda entry: entry.score, reverse=True):
            cluster_key = normalize_for_match(item.name) or item.entity_id
            existing = canonical_clusters.get(cluster_key)
            if existing is None or item.score > existing.score:
                canonical_clusters[cluster_key] = item
        ranked = sorted(canonical_clusters.values(), key=lambda item: item.score, reverse=True)
        return ranked[:20]

    @staticmethod
    def to_related_nodes(candidates: list[CandidateEntity]) -> List[RelatedNodeItem]:
        return [
            RelatedNodeItem(
                id=candidate.entity_id,
                type=candidate.type,
                display_name=candidate.name,
            )
            for candidate in candidates
        ]

    @staticmethod
    def to_matched_entities(candidates: list[CandidateEntity]) -> List[MatchedEntityItem]:
        return [
            MatchedEntityItem(
                id=candidate.entity_id,
                type=candidate.type,
                display_name=candidate.name,
            )
            for candidate in candidates
        ]
