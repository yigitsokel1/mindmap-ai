"""Question interpretation rules for semantic query planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class InterpretedQuestion:
    """Deterministic representation of a user query."""

    intent: str
    entity_hints: List[str]
    relation_hints: List[str]
    document_constraints: dict
    disambiguation_terms: List[str]


class QuestionInterpreter:
    """Interpret natural language questions into structured query hints."""

    _STOPWORDS = {
        "what",
        "which",
        "where",
        "when",
        "why",
        "how",
        "the",
        "this",
        "that",
        "these",
        "those",
        "about",
        "from",
        "with",
        "into",
        "paper",
        "document",
        "show",
        "tell",
        "explain",
        "list",
        "for",
        "and",
        "are",
        "does",
        "using",
        "used",
    }

    def interpret(self, question: str, document_id: Optional[str] = None) -> InterpretedQuestion:
        normalized = question.lower()
        tokens = re.findall(r"[a-zA-Z0-9_]+", normalized)
        intent = self._detect_intent(normalized)
        entity_hints = self._extract_entity_hints(question, tokens)
        relation_hints = self._detect_relation_hints(normalized)
        document_constraints = {"document_id": document_id} if document_id else {}
        disambiguation_terms = [token for token in tokens if token not in self._STOPWORDS and len(token) > 3][:6]
        return InterpretedQuestion(
            intent=intent,
            entity_hints=entity_hints,
            relation_hints=relation_hints,
            document_constraints=document_constraints,
            disambiguation_terms=disambiguation_terms,
        )

    def _detect_intent(self, text: str) -> str:
        if any(term in text for term in ("citation", "cited", "reference", "refs", "bibliography")):
            return "CITATION_BASIS"
        if any(term in text for term in ("method", "algorithm", "approach", "technique", "architecture")):
            return "METHOD_USAGE"
        if any(term in text for term in ("problem", "challenge", "limitation", "issue", "bottleneck")):
            return "PROBLEM"
        if any(term in text for term in ("relation", "related", "connect", "link", "between")):
            return "RELATION_LOOKUP"
        return "SUMMARY"

    @staticmethod
    def _detect_relation_hints(text: str) -> List[str]:
        relation_map = {
            "USES": ("use", "uses", "used", "utilize", "apply"),
            "IMPROVES": ("improve", "improves", "better", "outperform", "successful", "benefit"),
            "BASED_ON": ("based", "derived", "built on", "inspired"),
            "APPLIED_TO": ("applied", "application", "task", "used in"),
        }
        hints: List[str] = []
        for relation, keywords in relation_map.items():
            if any(keyword in text for keyword in keywords):
                hints.append(relation)
        return hints

    def _extract_entity_hints(self, question: str, tokens: List[str]) -> List[str]:
        phrase_matches = re.findall(r"\b([A-Z][a-zA-Z0-9_-]+(?:\s+[A-Z][a-zA-Z0-9_-]+)*)\b", question)
        entities = [match.strip().lower() for match in phrase_matches if match.strip()]
        entities.extend([token for token in tokens if len(token) > 2 and token not in self._STOPWORDS])
        deduped: List[str] = []
        seen = set()
        for item in entities:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped[:10]
