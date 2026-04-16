"""Canonical-safe normalization utilities.

Precision-first: keep transformations conservative to avoid false merges.
"""

from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[^a-z0-9]+")
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?]+$")
STOPWORDS = {"the", "a", "an"}


def normalize_for_match(value: str | None) -> str:
    """Normalize names for canonical matching without aggressive simplification."""
    if not value:
        return ""
    lowered = value.strip().lower().replace("_", " ").replace("-", " ")
    lowered = TRAILING_PUNCT_RE.sub("", lowered)
    compact = TOKEN_RE.sub(" ", lowered)
    normalized = " ".join(compact.split())
    return _trim_safe_stopwords(_light_singularize(normalized))


def _light_singularize(text: str) -> str:
    words: list[str] = []
    for part in text.split():
        if len(part) > 4 and part.endswith("ies"):
            words.append(f"{part[:-3]}y")
        elif len(part) > 3 and part.endswith("s") and not part.endswith(("ss", "us")):
            words.append(part[:-1])
        else:
            words.append(part)
    return " ".join(words)


def _trim_safe_stopwords(text: str) -> str:
    parts = text.split()
    if not parts:
        return text
    if len(parts) >= 2 and parts[0] in STOPWORDS:
        parts = parts[1:]
    if len(parts) >= 2 and parts[-1] in STOPWORDS:
        parts = parts[:-1]
    return " ".join(parts)
