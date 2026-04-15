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
        entity_hints = [token for token in tokens if len(token) > 2 and token not in self._STOPWORDS][:8]
        relation_hints = self._detect_relation_hints(normalized)
        document_constraints = {"document_id": document_id} if document_id else {}
        return InterpretedQuestion(
            intent=intent,
            entity_hints=entity_hints,
            relation_hints=relation_hints,
            document_constraints=document_constraints,
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
            "uses": ("uses", "used", "utilize", "apply"),
            "improves": ("improve", "improves", "better", "outperform"),
            "supports": ("support", "supports", "evidence"),
            "compares": ("compare", "versus", "vs", "against"),
            "addresses": ("address", "solve", "problem", "challenge"),
            "cites": ("cite", "citation", "reference"),
        }
        hints: List[str] = []
        for relation, keywords in relation_map.items():
            if any(keyword in text for keyword in keywords):
                hints.append(relation)
        return hints
