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
        local_candidates = self._fetch_local_candidates(tokens, document_id, node_types, interpreted.intent)
        canonical_candidates = self.reader.lookup_canonical_candidates(tokens)
        boosted = self._apply_disambiguation_boost(
            [*local_candidates, *canonical_candidates],
            interpreted.disambiguation_terms,
        )
        merged = self._merge_candidates(boosted)
        deduped = self._dedupe_canonical(merged)
        return self._select_representatives(deduped)

    def _fetch_local_candidates(
        self,
        tokens: list[str],
        document_id: str | None,
        node_types: list[str],
        intent: str,
    ) -> List[CandidateEntity]:
        local = self.reader.find_candidate_entities(
            tokens=tokens,
            document_id=document_id,
            node_types=node_types,
        )
        if local:
            return local
        # Avoid noisy fallback for weak or out-of-domain tokenization.
        if len(tokens) <= 1:
            return []
        return self.reader.find_fallback_entities(
            document_id=document_id,
            node_types=node_types,
            intent=intent,
        )

    @staticmethod
    def _apply_disambiguation_boost(
        candidates: List[CandidateEntity],
        disambiguation_terms: list[str],
    ) -> List[CandidateEntity]:
        boosted: List[CandidateEntity] = []
        terms = {term.lower() for term in disambiguation_terms}
        for candidate in candidates:
            if terms and any(term in candidate.name.lower() for term in terms):
                boosted.append(
                    candidate.model_copy(
                        update={
                            "score": min(1.0, candidate.score + 0.1),
                            "match_reason": f"{candidate.match_reason}|disambiguation_context",
                        }
                    )
                )
                continue
            boosted.append(candidate)
        return boosted

    @staticmethod
    def _merge_candidates(candidates: List[CandidateEntity]) -> List[CandidateEntity]:
        merged_by_id: dict[str, CandidateEntity] = {}
        for candidate in candidates:
            existing = merged_by_id.get(candidate.entity_id)
            if existing is None:
                merged_by_id[candidate.entity_id] = candidate
                continue
            if candidate.score > existing.score:
                merged_by_id[candidate.entity_id] = candidate
                continue
            if candidate.source == "canonical-ready" and existing.source != "canonical-ready":
                merged_by_id[candidate.entity_id] = candidate
        return list(merged_by_id.values())

    @staticmethod
    def _dedupe_canonical(candidates: List[CandidateEntity]) -> List[CandidateEntity]:
        canonical_clusters: dict[str, CandidateEntity] = {}
        for item in sorted(candidates, key=lambda entry: entry.score, reverse=True):
            cluster_key = normalize_for_match(item.name) or item.entity_id
            existing = canonical_clusters.get(cluster_key)
            if existing is None or item.score > existing.score:
                canonical_clusters[cluster_key] = item
        return list(canonical_clusters.values())

    @staticmethod
    def _select_representatives(candidates: List[CandidateEntity], limit: int = 20) -> List[CandidateEntity]:
        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        return ranked[:limit]

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
