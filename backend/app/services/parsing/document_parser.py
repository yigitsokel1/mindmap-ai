"""Document-level parser.

Combines PDF parsing with section detection, passage splitting,
and reference parsing to produce section-aware PassageRecords.

Flow:
  PDF → pages → section detection → reference boundary
    → per-section passage splitting (body only)
    → reference parsing
    → ParseResult
"""

import logging
import uuid
from dataclasses import dataclass, field

from backend.app.schemas.citation import CitationLinkRecord, InlineCitationRecord
from backend.app.schemas.document_structure import ReferenceRecord, SectionRecord
from backend.app.schemas.passage import PassageRecord
from backend.app.services.parsing.inline_citation_parser import parse_inline_citations
from backend.app.services.parsing.pdf_parser import PageRecord, parse_pdf
from backend.app.services.parsing.passage_splitter import PassageSplitter
from backend.app.services.parsing.section_detector import detect_sections
from backend.app.services.parsing.reference_parser import (
    find_references_boundary,
    parse_references,
)

logger = logging.getLogger(__name__)


@dataclass
class DocumentParseResult:
    """Result of document parsing."""

    pages: list[PageRecord] = field(default_factory=list)
    passages: list[PassageRecord] = field(default_factory=list)
    sections: list[SectionRecord] = field(default_factory=list)
    references: list[ReferenceRecord] = field(default_factory=list)
    inline_citations: list[InlineCitationRecord] = field(default_factory=list)
    citation_links: list[CitationLinkRecord] = field(default_factory=list)


# Backward-compatible alias.
ParseResult = DocumentParseResult


def parse_document(
    file_path: str,
    document_id: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> DocumentParseResult:
    """Parse a PDF into section-aware PassageRecords.

    Flow:
      1. Extract pages from PDF
      2. Detect section boundaries
      3. Find references boundary
      4. Split body sections into passages (with section context)
      5. Parse reference entries
      6. Return ParseResult with passages, sections, references

    Args:
        file_path: Path to the PDF file.
        document_id: UID for the document.
        chunk_size: Max characters per passage.
        chunk_overlap: Character overlap between passages.

    Returns:
        ParseResult with passages, sections, and references.
    """
    pages = parse_pdf(file_path)
    splitter = PassageSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # Detect sections
    sections = detect_sections(pages, document_id=document_id)

    # Find references boundary
    ref_ordinal = find_references_boundary(sections) if sections else None

    # Parse references if boundary found
    references: list[ReferenceRecord] = []
    if ref_ordinal is not None:
        ref_section = sections[ref_ordinal]
        references = parse_references(
            pages, ref_section.page_start, document_id=document_id
        )

    # Build passages and inline citations
    passages: list[PassageRecord] = []
    inline_citations: list[InlineCitationRecord] = []
    global_index = 0

    if sections:
        # Section-aware splitting
        for section in sections:
            is_reference = (
                ref_ordinal is not None and section.ordinal >= ref_ordinal
            )
            content_type = "reference" if is_reference else "body"

            # Skip splitting reference sections — they're stored as ReferenceRecords
            if is_reference:
                continue

            # Collect page text for this section's page range
            section_text = _collect_section_text(pages, section, sections)

            if not section_text.strip():
                continue

            # Split into passages
            page_passages = splitter.split(section_text)

            for text in page_passages:
                passage = PassageRecord(
                    passage_id=f"pass:{uuid.uuid4().hex[:12]}",
                    document_id=document_id,
                    index=global_index,
                    text=text,
                    page_number=section.page_start,
                    section_title=section.title,
                    section_id=section.section_id,
                    content_type=content_type,
                )
                passages.append(passage)
                inline_citations.extend(
                    parse_inline_citations(
                        passage_text=text,
                        document_id=document_id,
                        passage_id=passage.passage_id,
                        page_number=passage.page_number,
                    )
                )
                global_index += 1
    else:
        # Fallback: no sections detected — flat page-by-page splitting
        for page in pages:
            page_passages = splitter.split(page.text)

            for text in page_passages:
                passage = PassageRecord(
                    passage_id=f"pass:{uuid.uuid4().hex[:12]}",
                    document_id=document_id,
                    index=global_index,
                    text=text,
                    page_number=page.page_number,
                )
                passages.append(passage)
                inline_citations.extend(
                    parse_inline_citations(
                        passage_text=text,
                        document_id=document_id,
                        passage_id=passage.passage_id,
                        page_number=passage.page_number,
                    )
                )
                global_index += 1

    citation_links = _link_inline_citations_to_references(inline_citations, references)

    logger.info(
        "Document %s: %d pages, %d sections, %d body passages, %d references, %d citations, %d links",
        document_id,
        len(pages),
        len(sections),
        len(passages),
        len(references),
        len(inline_citations),
        len(citation_links),
    )

    return DocumentParseResult(
        pages=pages,
        passages=passages,
        sections=sections,
        references=references,
        inline_citations=inline_citations,
        citation_links=citation_links,
    )


def _collect_section_text(
    pages: list[PageRecord],
    section: SectionRecord,
    all_sections: list[SectionRecord],
) -> str:
    """Collect text belonging to a specific section.

    Extracts text from page_start to page_end of the section.
    On the first page, text starts after the section heading.
    On shared pages, text stops before the next section heading.
    """
    texts: list[str] = []

    for page in pages:
        if page.page_number < section.page_start:
            continue
        if page.page_number > section.page_end:
            break

        page_text = page.text

        # On the first page, skip text before the section heading
        if page.page_number == section.page_start:
            # Find the heading in the page text
            import re
            heading_escaped = re.escape(section.title)
            match = re.search(heading_escaped, page_text, re.IGNORECASE)
            if match:
                page_text = page_text[match.end():]

        texts.append(page_text)

    return "\n".join(texts)


def _link_inline_citations_to_references(
    inline_citations: list[InlineCitationRecord],
    references: list[ReferenceRecord],
) -> list[CitationLinkRecord]:
    """Create citation links from inline mentions to reference entries."""
    if not inline_citations or not references:
        return []

    links: list[CitationLinkRecord] = []
    refs_by_numeric = {
        ref.citation_key_numeric: ref
        for ref in references
        if ref.citation_key_numeric is not None
    }
    refs_by_author_year = {}
    for ref in references:
        if not ref.citation_key_author_year:
            continue
        for key in ref.citation_key_author_year:
            refs_by_author_year[key] = ref

    for citation in inline_citations:
        if citation.reference_keys:
            for key in citation.reference_keys:
                if not key.isdigit():
                    continue
                matched_ref = refs_by_numeric.get(int(key))
                if matched_ref:
                    links.append(
                        CitationLinkRecord(
                            inline_citation_id=citation.citation_id,
                            reference_entry_id=matched_ref.reference_id,
                            confidence=1.0,
                        )
                    )
            continue

        if citation.reference_labels:
            for label in citation.reference_labels:
                matched_ref = refs_by_author_year.get(label)
                if matched_ref:
                    links.append(
                        CitationLinkRecord(
                            inline_citation_id=citation.citation_id,
                            reference_entry_id=matched_ref.reference_id,
                            confidence=0.7,
                        )
                    )

    return links
