"""Citation writer for semantic graph persistence."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class CitationWriter:
    """Persists inline citations and citation-reference links."""

    def write_inline_citations(self, session, citations, citation_links) -> dict:
        """Write inline citations and reference links with normalized counts."""
        citations_written = 0
        citation_links_written = 0
        unlinked_citations = 0

        for citation in citations:
            result = session.run(
                "MERGE (c:InlineCitation {uid: $uid}) "
                "ON CREATE SET c.raw_text = $raw_text, "
                "             c.citation_style = $citation_style, "
                "             c.start_char = $start_char, "
                "             c.end_char = $end_char, "
                "             c.page_number = $page_number, "
                "             c.reference_keys = $reference_keys, "
                "             c.reference_labels = $reference_labels, "
                "             c.created_at = $now "
                "ON MATCH SET c.raw_text = $raw_text, "
                "             c.citation_style = $citation_style, "
                "             c.start_char = $start_char, "
                "             c.end_char = $end_char, "
                "             c.page_number = $page_number, "
                "             c.reference_keys = $reference_keys, "
                "             c.reference_labels = $reference_labels "
                "WITH c "
                "MATCH (p:Passage {uid: $passage_uid}) "
                "MERGE (p)-[:HAS_INLINE_CITATION]->(c) "
                "RETURN p.uid AS passage_uid, c.uid AS citation_uid",
                {
                    "uid": citation.citation_id,
                    "raw_text": citation.raw_text,
                    "citation_style": citation.citation_style,
                    "start_char": citation.start_char,
                    "end_char": citation.end_char,
                    "page_number": citation.page_number,
                    "reference_keys": citation.reference_keys or [],
                    "reference_labels": citation.reference_labels or [],
                    "passage_uid": citation.passage_id,
                    "now": _now_iso(),
                },
            )
            if result.single():
                citations_written += 1
            else:
                logger.warning(
                    "Inline citation %s could not be linked: missing Passage %s",
                    citation.citation_id,
                    citation.passage_id,
                )
                unlinked_citations += 1

        for link in citation_links:
            result = session.run(
                "MATCH (c:InlineCitation {uid: $citation_uid}) "
                "MATCH (r:ReferenceEntry {uid: $reference_uid}) "
                "MERGE (c)-[rel:REFERS_TO]->(r) "
                "SET rel.confidence = $confidence "
                "RETURN rel",
                {
                    "citation_uid": link.inline_citation_id,
                    "reference_uid": link.reference_entry_id,
                    "confidence": link.confidence,
                },
            )
            if result.single():
                citation_links_written += 1

        return {
            "citations_written": citations_written,
            "citation_links_written": citation_links_written,
            "unlinked_citations": unlinked_citations,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
