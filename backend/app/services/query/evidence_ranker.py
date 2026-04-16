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
        "results": 1.0,
        "discussion": 0.8,
        "references": -0.8,
        "unknown": 0.0,
    }
    _CITATION_INTENT_MULTIPLIER = {
        "CITATION_BASIS": 2.0,
        "METHOD_USAGE": 1.2,
        "RELATION_LOOKUP": 1.0,
        "SUMMARY": 0.9,
        "PROBLEM": 0.8,
    }

    def rank(
        self,
        evidences: Sequence[SemanticEvidenceItem],
        interpreted: InterpretedQuestion,
        candidate_names: Sequence[str],
    ) -> List[SemanticEvidenceItem]:
        duplicate_counts = {}
        document_counts = {}
        for item in evidences:
            key = self._canonical_snippet(item.snippet)
            duplicate_counts[key] = duplicate_counts.get(key, 0) + 1
            doc_key = (item.document_id or item.document_name or "").strip().lower()
            document_counts[doc_key] = document_counts.get(doc_key, 0) + 1

        scored = []
        for item in evidences:
            score = 0.0
            lower_snippet = (item.snippet or "").lower()
            if any(name and name.lower() in lower_snippet for name in candidate_names):
                score += 2.0
            score += self._section_weight(item.section, interpreted.intent)
            if item.citation_label or item.reference_entry_id:
                citation_weight = self._CITATION_INTENT_MULTIPLIER.get(interpreted.intent, 1.0)
                score += 1.4 * citation_weight
            score += max(0.0, min(1.0, item.confidence)) * 1.8
            if interpreted.relation_hints and any(
                hint in (item.relation_type or "").lower() for hint in interpreted.relation_hints
            ):
                score += 1.5
            score += self._relation_alignment_bonus(item.relation_type, interpreted.intent)
            score += self._diversity_bonus(item)
            duplicates = duplicate_counts.get(self._canonical_snippet(item.snippet), 0)
            if duplicates > 1:
                # Strongly demote repeated passages so top-k remains diverse.
                score -= min(3.0, 2.2 + (0.6 * (duplicates - 2)))
            doc_key = (item.document_id or item.document_name or "").strip().lower()
            if doc_key and document_counts.get(doc_key, 0) > 1:
                score -= min(1.0, 0.35 * (document_counts[doc_key] - 1))
            scored.append((score, item))

        scored.sort(key=lambda entry: entry[0], reverse=True)
        return [item for _, item in scored]

    def _section_weight(self, section: str | None, intent: str) -> float:
        normalized = (section or "unknown").strip().lower()
        base = self._BASE_SECTION_WEIGHTS.get(normalized, self._BASE_SECTION_WEIGHTS["unknown"])
        if intent == "METHOD_USAGE" and normalized == "methods":
            return base + 2.4
        if intent == "METHOD_USAGE" and normalized == "abstract":
            return base - 1.4
        if intent == "SUMMARY" and normalized == "conclusion":
            return base + 0.8
        if intent == "PROBLEM" and normalized in {"abstract", "discussion"}:
            return base + 0.8
        if intent == "CITATION_BASIS" and normalized == "references":
            return base + 1.6
        if intent == "RELATION_LOOKUP" and normalized in {"results", "methods"}:
            return base + 0.9
        return base

    @staticmethod
    def _canonical_snippet(snippet: str) -> str:
        return " ".join((snippet or "").strip().lower().split())

    @staticmethod
    def _diversity_bonus(item: SemanticEvidenceItem) -> float:
        section = (item.section or "").strip().lower()
        doc_present = bool((item.document_id or item.document_name or "").strip())
        section_bonus = 0.3 if section and section != "unknown" else 0.0
        document_bonus = 0.2 if doc_present else 0.0
        return section_bonus + document_bonus

    @staticmethod
    def _relation_alignment_bonus(relation_type: str | None, intent: str) -> float:
        rel = (relation_type or "").lower()
        if not rel:
            return 0.0
        if intent == "METHOD_USAGE" and any(token in rel for token in ("method", "use", "implement")):
            return 1.1
        if intent == "PROBLEM" and any(token in rel for token in ("problem", "challenge", "limitation")):
            return 1.1
        if intent == "RELATION_LOOKUP":
            return 0.8
        if intent == "CITATION_BASIS" and any(token in rel for token in ("cite", "support", "reference")):
            return 0.9
        return 0.0
