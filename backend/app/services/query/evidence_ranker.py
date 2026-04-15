"""Evidence ranking contract for semantic query responses."""

from __future__ import annotations

from typing import List, Sequence

from backend.app.schemas.semantic_query import SemanticEvidenceItem
from backend.app.services.query.question_interpreter import InterpretedQuestion


class EvidenceRanker:
    """Rule-based evidence ranker using deterministic scoring signals."""

    _BASE_SECTION_WEIGHTS = {
        "abstract": 2.0,
        "methods": 1.0,
        "conclusion": 1.2,
        "references": -0.8,
        "unknown": 0.0,
    }

    def rank(
        self,
        evidences: Sequence[SemanticEvidenceItem],
        interpreted: InterpretedQuestion,
        candidate_names: Sequence[str],
    ) -> List[SemanticEvidenceItem]:
        duplicate_counts = {}
        for item in evidences:
            key = self._canonical_snippet(item.snippet)
            duplicate_counts[key] = duplicate_counts.get(key, 0) + 1

        scored = []
        for item in evidences:
            score = 0.0
            lower_snippet = (item.snippet or "").lower()
            if any(name and name.lower() in lower_snippet for name in candidate_names):
                score += 2.0
            score += self._section_weight(item.section, interpreted.intent)
            if item.citation_label or item.reference_entry_id:
                score += 1.4
            score += max(0.0, min(1.0, item.confidence)) * 1.8
            if interpreted.relation_hints and any(
                hint in (item.relation_type or "").lower() for hint in interpreted.relation_hints
            ):
                score += 1.5
            duplicates = duplicate_counts.get(self._canonical_snippet(item.snippet), 0)
            if duplicates > 1:
                score -= min(1.5, 0.5 * (duplicates - 1))
            scored.append((score, item))

        scored.sort(key=lambda entry: entry[0], reverse=True)
        return [item for _, item in scored]

    def _section_weight(self, section: str | None, intent: str) -> float:
        normalized = (section or "unknown").strip().lower()
        base = self._BASE_SECTION_WEIGHTS.get(normalized, self._BASE_SECTION_WEIGHTS["unknown"])
        if intent == "METHOD_USAGE" and normalized == "methods":
            return base + 1.2
        if intent == "SUMMARY" and normalized == "conclusion":
            return base + 0.8
        return base

    @staticmethod
    def _canonical_snippet(snippet: str) -> str:
        return " ".join((snippet or "").strip().lower().split())
