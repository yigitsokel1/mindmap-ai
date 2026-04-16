"""Candidate selection helpers for semantic query orchestration."""

from __future__ import annotations

import re
from typing import List

from backend.app.schemas.semantic_query import CandidateEntity, MatchedEntityItem, RelatedNodeItem
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
        return [*local_candidates, *canonical_candidates]

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
