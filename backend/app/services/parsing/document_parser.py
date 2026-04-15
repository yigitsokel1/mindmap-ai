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
import asyncio
import uuid
import inspect
from dataclasses import dataclass, field
from typing import Callable

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

logger = logging.getLogger("uvicorn.error")


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
    chunk_size: int = 1600,
    chunk_overlap: int = 200,
    progress_callback: Callable[[str, dict | None], None] | None = None,
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
    _notify(progress_callback, "detecting_sections")
    sections = detect_sections(pages, document_id=document_id)

    # Find references boundary
    ref_ordinal = find_references_boundary(sections) if sections else None

    # Parse references if boundary found
    references: list[ReferenceRecord] = []
    if ref_ordinal is not None:
        _notify(progress_callback, "parsing_references")
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
                global_index += 1

    if passages:
        _notify(progress_callback, "parsing", {"subphase": "inline_citations"})
        inline_citations = _parse_inline_citations_parallel(passages, document_id)

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
    next_section = None
    for candidate in all_sections:
        if candidate.ordinal > section.ordinal:
            next_section = candidate
            break

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

        # If next section starts on this page, stop before its heading.
        if next_section and page.page_number == next_section.page_start:
            import re

            next_heading_escaped = re.escape(next_section.title)
            next_match = re.search(next_heading_escaped, page_text, re.IGNORECASE)
            if next_match:
                page_text = page_text[:next_match.start()]

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

    logger.info(
        "Citation linking summary: citations=%d references=%d links=%d unlinked=%d",
        len(inline_citations),
        len(references),
        len(links),
        max(len(inline_citations) - len({link.inline_citation_id for link in links}), 0),
    )
    return links


def _notify(
    progress_callback: Callable[[str, dict | None], None] | None,
    stage: str,
    details: dict | None = None,
) -> None:
    if not progress_callback:
        return
    maybe_awaitable = progress_callback(stage, details)
    if inspect.isawaitable(maybe_awaitable):
        try:
            asyncio.get_running_loop()
            has_running_loop = True
        except RuntimeError:
            has_running_loop = False
        if has_running_loop:
            asyncio.create_task(maybe_awaitable)
            return
        asyncio.run(maybe_awaitable)


def _parse_inline_citations_parallel(
    passages: list[PassageRecord],
    document_id: str,
) -> list[InlineCitationRecord]:
    """Parse inline citations concurrently across passages."""

    semaphore = asyncio.Semaphore(5)

    async def _parse_passage(passage: PassageRecord) -> list[InlineCitationRecord]:
        async with semaphore:
            return await asyncio.to_thread(
                parse_inline_citations,
                passage_text=passage.text,
                document_id=document_id,
                passage_id=passage.passage_id,
                page_number=passage.page_number,
            )

    async def _run() -> list[list[InlineCitationRecord]]:
        tasks = [_parse_passage(passage) for passage in passages]
        if not tasks:
            return []
        return await asyncio.gather(*tasks)

    try:
        asyncio.get_running_loop()
        has_running_loop = True
    except RuntimeError:
        has_running_loop = False

    if has_running_loop:
        grouped = [
            parse_inline_citations(
                passage_text=passage.text,
                document_id=document_id,
                passage_id=passage.passage_id,
                page_number=passage.page_number,
            )
            for passage in passages
        ]
    else:
        grouped = asyncio.run(_run())
    flattened: list[InlineCitationRecord] = []
    for items in grouped:
        flattened.extend(items)
    return flattened
