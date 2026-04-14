"""Reference parser for academic PDFs.

Detects the references section boundary and splits
the reference block into individual ReferenceRecord entries.
"""

import logging
import re
import uuid

from backend.app.schemas.document_structure import ReferenceRecord, SectionRecord
from backend.app.services.parsing.pdf_parser import PageRecord

logger = logging.getLogger(__name__)

# Patterns for splitting individual references
BRACKET_REF_PATTERN = re.compile(r"^\[(\d+)\]\s*", re.MULTILINE)
NUMBERED_REF_PATTERN = re.compile(r"^(\d+)\.\s+", re.MULTILINE)
LEADING_NUMERIC_KEY_PATTERN = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)\.)\s*")
AUTHOR_YEAR_CANDIDATE_PATTERN = re.compile(r"([A-Z][A-Za-z'\-]+)(?:\s+et\s+al\.)?.{0,40}\b((?:19|20)\d{2})\b")

# Year extraction: 4-digit year in range 1900-2099
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def find_references_boundary(sections: list[SectionRecord]) -> int | None:
    """Find the ordinal of the References section.

    Looks for the last section whose title matches "References"
    or "Bibliography" (case-insensitive).

    Args:
        sections: List of SectionRecord objects from section detector.

    Returns:
        Ordinal of the references section, or None if not found.
    """
    ref_ordinal = None
    for section in sections:
        title_lower = section.title.lower().strip()
        # Strip leading numbers like "7. References" → "references"
        cleaned = re.sub(r"^\d+\.?\d*\.?\s*", "", title_lower)
        if cleaned in ("references", "bibliography"):
            ref_ordinal = section.ordinal

    return ref_ordinal


def parse_references(
    pages: list[PageRecord],
    ref_start_page: int,
    document_id: str = "",
) -> list[ReferenceRecord]:
    """Parse reference entries from the references section pages.

    Concatenates text from ref_start_page onwards and splits into
    individual reference entries.

    Args:
        pages: All PageRecord objects from the document.
        ref_start_page: Page number where references begin.
        document_id: UID for the document.

    Returns:
        List of ReferenceRecord objects.
    """
    # Collect text from reference pages
    ref_texts = []
    for page in pages:
        if page.page_number >= ref_start_page:
            ref_texts.append(page.text)

    if not ref_texts:
        return []

    full_text = "\n".join(ref_texts)

    # Remove the "References" heading itself
    full_text = re.sub(
        r"^\s*(\d+\.?\s*)?(References|Bibliography)\s*\n",
        "",
        full_text,
        count=1,
        flags=re.IGNORECASE,
    )

    # Try bracket-style references first: [1] Author...
    entries = _split_by_pattern(full_text, BRACKET_REF_PATTERN)

    # Fallback to numbered-dot style: 1. Author...
    if not entries:
        entries = _split_by_pattern(full_text, NUMBERED_REF_PATTERN)

    # Last fallback: split on blank lines
    if not entries:
        entries = _split_by_blank_lines(full_text)

    # Build ReferenceRecords
    records: list[ReferenceRecord] = []
    for i, raw_text in enumerate(entries):
        raw_text = raw_text.strip()
        if not raw_text or len(raw_text) < 10:
            continue

        year = _extract_year(raw_text)
        title_guess = _extract_title_guess(raw_text)
        authors_guess = _extract_authors_guess(raw_text)
        citation_key_numeric = _extract_numeric_key(raw_text, i)
        citation_key_author_year = _build_author_year_keys(authors_guess, year)

        record = ReferenceRecord(
            reference_id=f"ref:{uuid.uuid4().hex[:12]}",
            document_id=document_id,
            raw_text=raw_text,
            order=i,
            year=year,
            title_guess=title_guess,
            authors_guess=authors_guess,
            citation_key_numeric=citation_key_numeric,
            citation_key_author_year=citation_key_author_year or None,
        )
        records.append(record)

    logger.info(
        "Parsed %d references from document %s",
        len(records),
        document_id,
    )
    return records


def _split_by_pattern(text: str, pattern: re.Pattern) -> list[str]:
    """Split text into entries using a numbered reference pattern."""
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return []

    entries: list[str] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entry_text = text[start:end].strip()
        entries.append(entry_text)

    return entries


def _split_by_blank_lines(text: str) -> list[str]:
    """Split text by blank lines as a last resort."""
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _extract_year(text: str) -> int | None:
    """Extract publication year from reference text.

    Returns the last 4-digit year found (usually the publication year).
    """
    matches = YEAR_PATTERN.findall(text)
    if matches:
        # findall returns the capture group, reconstruct full year
        all_years = YEAR_PATTERN.finditer(text)
        years = [int(m.group()) for m in all_years]
        if years:
            return years[-1]
    return None


def _extract_title_guess(text: str) -> str | None:
    """Guess the title from reference text.

    Heuristic: text between the first and second period,
    which in many citation styles contains the title.
    Returns None if extraction fails.
    """
    # Remove leading reference number like "[1]" or "1."
    cleaned = re.sub(r"^\[?\d+\]?\.\s*", "", text)

    # Split on periods
    parts = cleaned.split(".")

    if len(parts) >= 3:
        # Title is often the second segment (after author names)
        candidate = parts[1].strip()
        if 10 < len(candidate) < 300:
            return candidate

    return None


def _extract_numeric_key(text: str, fallback_order: int) -> int:
    match = LEADING_NUMERIC_KEY_PATTERN.match(text)
    if not match:
        return fallback_order + 1
    value = match.group(1) or match.group(2)
    if value and value.isdigit():
        return int(value)
    return fallback_order + 1


def _extract_authors_guess(text: str) -> list[str]:
    matches = list(AUTHOR_YEAR_CANDIDATE_PATTERN.finditer(text))
    if not matches:
        return []
    # V1 heuristic: keep first candidate surname as the reference lead author.
    first_surname = matches[0].group(1).strip()
    return [first_surname]


def _build_author_year_keys(authors_guess: list[str], year: int | None) -> list[str]:
    if not authors_guess or year is None:
        return []
    return [f"{authors_guess[0].lower()}:{year}"]
