"""Inline citation parser for body passages.

V1 parser is regex-first and extracts common academic citation forms:
- numeric brackets: [1], [2, 5, 8], [3-6]
- author-year parentheses: (Vaswani et al., 2017), (Smith, 2020; Doe, 2021)
"""

from __future__ import annotations

import re
import uuid

from backend.app.schemas.citation import InlineCitationRecord

NUMERIC_CITATION_PATTERN = re.compile(r"\[(\s*\d+(?:\s*[-,]\s*\d+)*\s*)\]")
AUTHOR_YEAR_BLOCK_PATTERN = re.compile(r"\(([^()]*\b(?:19|20)\d{2}\b[^()]*)\)")
AUTHOR_YEAR_LABEL_PATTERN = re.compile(
    r"([A-Z][A-Za-z'\-]+)(?:\s+et\s+al\.)?(?:\s+and\s+[A-Z][A-Za-z'\-]+)?\s*,\s*((?:19|20)\d{2})"
)


def parse_inline_citations(
    passage_text: str,
    document_id: str,
    passage_id: str,
    page_number: int,
) -> list[InlineCitationRecord]:
    """Parse inline citation mentions from one body passage."""
    citations: list[InlineCitationRecord] = []

    for match in NUMERIC_CITATION_PATTERN.finditer(passage_text):
        raw_text = match.group(0)
        keys = _expand_numeric_keys(match.group(1))
        citations.append(
            InlineCitationRecord(
                citation_id=f"cite:{uuid.uuid4().hex[:12]}",
                document_id=document_id,
                passage_id=passage_id,
                page_number=page_number,
                raw_text=raw_text,
                citation_style="numeric_bracket",
                start_char=match.start(),
                end_char=match.end(),
                reference_keys=keys or None,
                reference_labels=[f"[{key}]" for key in keys] if keys else None,
            )
        )

    for match in AUTHOR_YEAR_BLOCK_PATTERN.finditer(passage_text):
        raw_text = match.group(0)
        labels = _extract_author_year_labels(match.group(1))
        if not labels:
            continue
        citations.append(
            InlineCitationRecord(
                citation_id=f"cite:{uuid.uuid4().hex[:12]}",
                document_id=document_id,
                passage_id=passage_id,
                page_number=page_number,
                raw_text=raw_text,
                citation_style="author_year",
                start_char=match.start(),
                end_char=match.end(),
                reference_labels=labels,
            )
        )

    return sorted(citations, key=lambda item: item.start_char)


def _expand_numeric_keys(raw_body: str) -> list[str]:
    keys: list[str] = []
    for token in raw_body.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            bounds = [part.strip() for part in token.split("-", 1)]
            if len(bounds) != 2 or not bounds[0].isdigit() or not bounds[1].isdigit():
                continue
            start = int(bounds[0])
            end = int(bounds[1])
            if start > end:
                start, end = end, start
            keys.extend(str(value) for value in range(start, end + 1))
            continue
        if token.isdigit():
            keys.append(token)
    # Keep deterministic order while deduplicating.
    return list(dict.fromkeys(keys))


def _extract_author_year_labels(raw_body: str) -> list[str]:
    labels: list[str] = []
    for match in AUTHOR_YEAR_LABEL_PATTERN.finditer(raw_body):
        surname = match.group(1)
        year = match.group(2)
        labels.append(f"{surname.lower()}:{year}")
    return list(dict.fromkeys(labels))
