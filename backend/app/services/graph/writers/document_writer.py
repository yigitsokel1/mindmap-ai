"""Document and structure writer for semantic graph persistence."""

from backend.app.core.db import Neo4jDatabase
from backend.app.schemas.document_structure import ReferenceRecord, SectionRecord
from backend.app.schemas.passage import PassageRecord


class DocumentStructureWriter:
    """Writes document, passage, section, and reference structures."""

    def __init__(self) -> None:
        self.db = Neo4jDatabase()

    def ensure_document(self, session, document_id: str, metadata: dict | None = None) -> None:
        """MERGE a Document node with optional metadata."""
        params = {"uid": document_id, "now": _now_iso()}
        set_clauses = ["d.created_at = $now"]

        if metadata:
            for key in ("title", "file_name", "file_hash", "saved_file_name"):
                if key in metadata:
                    params[key] = metadata[key]
                    set_clauses.append(f"d.{key} = ${key}")

        on_create = ", ".join(set_clauses)
        session.run(
            f"MERGE (d:Document {{uid: $uid}}) "
            f"ON CREATE SET {on_create}",
            params,
        )

    def ensure_passage(self, session, passage: PassageRecord) -> None:
        """MERGE a Passage node and link to Document and optionally Section."""
        session.run(
            "MERGE (p:Passage {uid: $uid}) "
            "ON CREATE SET p.text = $text, p.index = $index, "
            "             p.page_number = $page_number, "
            "             p.section_title = $section_title, "
            "             p.content_type = $content_type, "
            "             p.extraction_status = 'completed' "
            "WITH p "
            "MATCH (d:Document {uid: $doc_uid}) "
            "MERGE (d)-[:HAS_PASSAGE {ordinal: $index}]->(p)",
            {
                "uid": passage.passage_id,
                "text": passage.text,
                "index": passage.index,
                "page_number": passage.page_number,
                "section_title": passage.section_title,
                "content_type": getattr(passage, "content_type", "body"),
                "doc_uid": passage.document_id,
            },
        )

        section_id = getattr(passage, "section_id", None)
        if section_id:
            session.run(
                "MATCH (s:Section {uid: $section_uid}) "
                "MATCH (p:Passage {uid: $passage_uid}) "
                "MERGE (s)-[:HAS_PASSAGE {ordinal: $index}]->(p)",
                {
                    "section_uid": section_id,
                    "passage_uid": passage.passage_id,
                    "index": passage.index,
                },
            )

    def write_sections(self, session, sections: list[SectionRecord], document_id: str) -> None:
        """Write Section nodes and link to Document."""
        for section in sections:
            self.ensure_section(session, section, document_id)

    def ensure_section(self, session, section: SectionRecord, document_id: str) -> None:
        """MERGE a Section node and link to Document."""
        session.run(
            "MERGE (s:Section {uid: $uid}) "
            "ON CREATE SET s.title = $title, s.ordinal = $ordinal, "
            "             s.level = $level, "
            "             s.page_start = $page_start, "
            "             s.page_end = $page_end, "
            "             s.created_at = $now "
            "WITH s "
            "MATCH (d:Document {uid: $doc_uid}) "
            "MERGE (d)-[:HAS_SECTION {ordinal: $ordinal}]->(s)",
            {
                "uid": section.section_id,
                "title": section.title,
                "ordinal": section.ordinal,
                "level": section.level,
                "page_start": section.page_start,
                "page_end": section.page_end,
                "doc_uid": document_id,
                "now": _now_iso(),
            },
        )

    def write_references(self, session, references: list[ReferenceRecord], document_id: str) -> None:
        """Write ReferenceEntry nodes and link to Document."""
        for ref in references:
            session.run(
                "MERGE (r:ReferenceEntry {uid: $uid}) "
                "ON CREATE SET r.raw_text = $raw_text, "
                "             r.order = $order, "
                "             r.year = $year, "
                "             r.title_guess = $title_guess, "
                "             r.authors_guess = $authors_guess, "
                "             r.citation_key_numeric = $citation_key_numeric, "
                "             r.citation_key_author_year = $citation_key_author_year, "
                "             r.created_at = $now "
                "ON MATCH SET r.raw_text = $raw_text, "
                "             r.year = $year, "
                "             r.title_guess = $title_guess, "
                "             r.authors_guess = $authors_guess, "
                "             r.citation_key_numeric = $citation_key_numeric, "
                "             r.citation_key_author_year = $citation_key_author_year "
                "WITH r "
                "MATCH (d:Document {uid: $doc_uid}) "
                "MERGE (d)-[:HAS_REFERENCE {order: $order}]->(r)",
                {
                    "uid": ref.reference_id,
                    "raw_text": ref.raw_text,
                    "order": ref.order,
                    "year": ref.year,
                    "title_guess": ref.title_guess,
                    "authors_guess": ref.authors_guess,
                    "citation_key_numeric": ref.citation_key_numeric,
                    "citation_key_author_year": ref.citation_key_author_year,
                    "doc_uid": document_id,
                    "now": _now_iso(),
                },
            )

    def check_duplicate_by_hash(self, file_hash: str) -> str | None:
        """Lookup an existing document uid by file hash."""
        if not self.db.driver:
            self.db.connect()
        result, _, _ = self.db.execute_query_with_retry(
            "MATCH (d:Document) WHERE d['file_hash'] = $hash RETURN d.uid AS uid LIMIT 1",
            {"hash": file_hash},
        )
        if not result:
            return None
        return result[0].get("uid")

    def store_document_metadata(
        self,
        document_id: str,
        file_name: str,
        file_hash: str,
        saved_name: str,
    ) -> None:
        """Persist document-level file metadata through the writer layer."""
        if not self.db.driver:
            self.db.connect()
        self.db.execute_query_with_retry(
            "MERGE (d:Document {uid: $uid}) "
            "SET d.file_name = $file_name, "
            "    d.file_hash = $file_hash, "
            "    d.saved_file_name = $saved_name",
            {
                "uid": document_id,
                "file_name": file_name,
                "file_hash": file_hash,
                "saved_name": saved_name,
            },
        )


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
