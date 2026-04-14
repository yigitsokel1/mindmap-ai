"""Heuristic section detector for academic PDFs.

Scans page text for common academic section headings and
produces SectionRecord objects with page boundaries.
"""

import logging
import re
import uuid

from backend.app.schemas.document_structure import SectionRecord
from backend.app.services.parsing.pdf_parser import PageRecord

logger = logging.getLogger(__name__)

# Known top-level section headings (case-insensitive)
KNOWN_HEADINGS = [
    "Abstract",
    "Introduction",
    "Related Work",
    "Background",
    "Preliminaries",
    "Methods",
    "Methodology",
    "Method",
    "Model",
    "Model Architecture",
    "Architecture",
    "Approach",
    "Proposed Method",
    "Experiments",
    "Experimental Setup",
    "Experimental Results",
    "Results",
    "Results and Discussion",
    "Evaluation",
    "Discussion",
    "Analysis",
    "Ablation Study",
    "Conclusion",
    "Conclusions",
    "Conclusions and Future Work",
    "Future Work",
    "References",
    "Bibliography",
    "Appendix",
    "Appendices",
    "Acknowledgments",
    "Acknowledgements",
    "Supplementary Material",
]

# Build regex alternation from known headings (escaped for regex)
_heading_alt = "|".join(re.escape(h) for h in KNOWN_HEADINGS)

# Pattern: optional numbering (e.g., "3.", "3.1", "A.") followed by heading text
# Matches at line start, allows trailing whitespace
SECTION_PATTERN = re.compile(
    rf"^(\d+\.?\d*\.?\s+|[A-Z]\.?\s+|[IVXLCDM]+\s+)?({_heading_alt})\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def detect_sections(
    pages: list[PageRecord], document_id: str = ""
) -> list[SectionRecord]:
    """Detect section boundaries from page text.

    Scans each page for lines matching known academic section headings.
    Returns SectionRecord objects with page_start/page_end set.

    Args:
        pages: List of PageRecord objects from pdf_parser.
        document_id: UID for the document (used in SectionRecord).

    Returns:
        List of SectionRecord objects sorted by ordinal.
        Empty list if no sections detected.
    """
    raw_matches: list[tuple[int, str, int]] = []  # (page_number, title, level)

    for page in pages:
        for match in SECTION_PATTERN.finditer(page.text):
            numbering = match.group(1) or ""
            heading = match.group(2)

            # Build full title with numbering
            title = (numbering + heading).strip()

            # Determine level from numbering
            level = _detect_level(numbering.strip())

            raw_matches.append((page.page_number, title, level))

    if not raw_matches:
        logger.info("No sections detected in document %s", document_id)
        return []

    # Deduplicate: if same heading appears on same page, keep first
    seen: set[tuple[int, str]] = set()
    unique_matches: list[tuple[int, str, int]] = []
    for page_num, title, level in raw_matches:
        key = (page_num, title.lower())
        if key not in seen:
            seen.add(key)
            unique_matches.append((page_num, title, level))

    # Build SectionRecords with page boundaries
    last_page = max(p.page_number for p in pages)
    sections: list[SectionRecord] = []

    for i, (page_num, title, level) in enumerate(unique_matches):
        # page_end = page before next section starts, or last page
        if i + 1 < len(unique_matches):
            page_end = unique_matches[i + 1][0]
            # If next section starts on same page, end is same page
            # Otherwise, end is page before next section
            if page_end > page_num:
                page_end = page_end
            # Keep page_end as the page where next section starts
            # (the passage splitter will handle exact boundaries)
        else:
            page_end = last_page

        section = SectionRecord(
            section_id=f"sec:{uuid.uuid4().hex[:12]}",
            document_id=document_id,
            title=title,
            level=level,
            ordinal=i,
            page_start=page_num,
            page_end=page_end,
        )
        sections.append(section)

    logger.info(
        "Detected %d sections in document %s: %s",
        len(sections),
        document_id,
        [s.title for s in sections],
    )
    return sections


def _detect_level(numbering: str) -> int:
    """Determine heading level from numbering prefix.

    "3" or "3." → level 1
    "3.1" or "3.1." → level 2
    "3.1.2" → level 3
    No numbering → level 1
    """
    if not numbering:
        return 1

    # Count dots to determine depth
    # "3." has 1 dot → level 1
    # "3.1" has 1 dot → level 2
    # "3.1." has 2 dots → level 2
    parts = numbering.rstrip(".").split(".")
    parts = [p for p in parts if p.strip()]

    if len(parts) <= 1:
        return 1
    return len(parts)
