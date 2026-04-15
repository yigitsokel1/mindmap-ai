"""Graph writer for persisting extraction results to Neo4j.

V2 (Sprint 3): Writes typed entity nodes, reified RelationInstance
nodes, Evidence nodes, and structural Document/Passage nodes.

Graph pattern for provenance:
    (source:Entity)-[:OUT_REL]->(ri:RelationInstance)-[:TO]->(target:Entity)
    (e:Evidence)-[:SUPPORTS]->(ri:RelationInstance)
    (e:Evidence)-[:FROM_PASSAGE]->(p:Passage)
"""

import logging
import time
from datetime import datetime, timezone

from backend.app.core.db import Neo4jDatabase
from backend.app.domain.identity import build_entity_uid, build_relation_instance_uid
from backend.app.schemas.citation import CitationLinkRecord, InlineCitationRecord
from backend.app.schemas.document_structure import ReferenceRecord, SectionRecord
from backend.app.schemas.extraction import ExtractionResult
from backend.app.schemas.passage import PassageRecord
from backend.app.services.graph.writers.document_writer import DocumentStructureWriter
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

logger = logging.getLogger(__name__)

ENTITY_LABELS = {
    "Concept", "Method", "Dataset", "Metric", "Task", "Author", "Institution",
}


class GraphWriter:
    """Writes normalized extraction results to Neo4j with provenance."""

    def __init__(self):
        self.db = Neo4jDatabase()
        self.document_writer = DocumentStructureWriter()

    def write(
        self,
        extraction: ExtractionResult,
        passage: PassageRecord,
        document_metadata: dict | None = None,
        citation_metadata: dict | None = None,
    ) -> dict:
        """Write extraction results to Neo4j.

        Creates/merges: Document, Passage, typed entity nodes,
        RelationInstance nodes, Evidence nodes, and all connecting edges.

        Args:
            extraction: Validated and normalized extraction result.
            passage: PassageRecord with structural metadata.
            document_metadata: Optional dict with title, file_name, file_hash, saved_file_name.

        Returns:
            dict with counts of entities, relations, and evidence written.
        """
        entity_count = 0
        relation_count = 0
        evidence_count = 0

        with self.db.driver.session() as session:
            # --- Structural writes ---
            self._ensure_document(session, passage.document_id, document_metadata)
            self._ensure_passage(session, passage)

            # --- Semantic entity writes ---
            for entity in extraction.entities:
                if entity.type not in ENTITY_LABELS:
                    continue
                canonical = entity.canonical_name or entity.name
                uid = build_entity_uid(entity.type, canonical)
                self._write_entity(session, entity, uid)
                entity_count += 1

            # --- Relation + Evidence writes ---
            for rel in extraction.relations:
                source_uid = build_entity_uid(
                    self._find_entity_type(extraction, rel.source), rel.source
                )
                target_uid = build_entity_uid(
                    self._find_entity_type(extraction, rel.target), rel.target
                )

                ri_uid = build_relation_instance_uid(rel.type, source_uid, target_uid)
                ev_uid = f"ev:{ri_uid}:{passage.passage_id}"

                wrote_ri = self._write_relation_instance(
                    session, ri_uid, rel, source_uid, target_uid
                )
                if wrote_ri:
                    relation_count += 1
                    self._write_evidence(
                        session,
                        ev_uid,
                        ri_uid,
                        passage,
                        rel.confidence,
                        citation_metadata=citation_metadata,
                    )
                    evidence_count += 1

        logger.info(
            "Wrote %d entities, %d relations, %d evidence for passage %s",
            entity_count, relation_count, evidence_count, passage.passage_id,
        )
        return {
            "entities_written": entity_count,
            "relations_written": relation_count,
            "evidence_written": evidence_count,
        }

    def write_batch(
        self,
        batch_items: list[tuple[ExtractionResult, PassageRecord, dict | None]],
    ) -> dict:
        """Write a batch of passage extractions using a single session."""
        if not self.db.driver:
            self.db.connect()
        retries = 3
        for attempt in range(1, retries + 1):
            entities_written = 0
            relations_written = 0
            evidence_written = 0
            try:
                with self.db.driver.session() as session:
                    for extraction, passage, citation_metadata in batch_items:
                        self._ensure_document(session, passage.document_id, None)
                        self._ensure_passage(session, passage)
                        for entity in extraction.entities:
                            if entity.type not in ENTITY_LABELS:
                                continue
                            canonical = entity.canonical_name or entity.name
                            uid = build_entity_uid(entity.type, canonical)
                            self._write_entity(session, entity, uid)
                            entities_written += 1
                        for rel in extraction.relations:
                            source_uid = build_entity_uid(
                                self._find_entity_type(extraction, rel.source), rel.source
                            )
                            target_uid = build_entity_uid(
                                self._find_entity_type(extraction, rel.target), rel.target
                            )
                            ri_uid = build_relation_instance_uid(rel.type, source_uid, target_uid)
                            ev_uid = f"ev:{ri_uid}:{passage.passage_id}"
                            wrote_ri = self._write_relation_instance(
                                session, ri_uid, rel, source_uid, target_uid
                            )
                            if wrote_ri:
                                relations_written += 1
                                self._write_evidence(
                                    session,
                                    ev_uid,
                                    ri_uid,
                                    passage,
                                    rel.confidence,
                                    citation_metadata=citation_metadata,
                                )
                                evidence_written += 1
                return {
                    "entities_written": entities_written,
                    "relations_written": relations_written,
                    "evidence_written": evidence_written,
                }
            except (TransientError, ServiceUnavailable, SessionExpired) as exc:
                if attempt == retries:
                    raise
                delay_s = 0.5 * attempt
                logger.warning(
                    "Retrying write_batch after transient Neo4j error attempt=%d/%d delay=%.2fs error=%s",
                    attempt,
                    retries,
                    delay_s,
                    exc,
                )
                time.sleep(delay_s)

    # --- Private methods ---

    def _ensure_document(self, session, document_id: str, metadata: dict | None = None):
        """MERGE a Document node with optional metadata."""
        self.document_writer.ensure_document(session, document_id, metadata)

    def _ensure_passage(self, session, passage: PassageRecord):
        """MERGE a Passage node and link to Document and optionally Section."""
        self.document_writer.ensure_passage(session, passage)

    def _write_entity(self, session, entity, uid: str):
        """MERGE a typed entity node by UID."""
        label = entity.type
        aliases = entity.aliases or []

        session.run(
            f"MERGE (e:{label} {{uid: $uid}}) "
            f"ON CREATE SET e.canonical_name = $canonical, "
            f"             e.name = $name, "
            f"             e.aliases = $aliases, "
            f"             e.confidence = $confidence, "
            f"             e.created_at = $now "
            f"ON MATCH SET e.aliases = "
            f"  [x IN e.aliases + $aliases WHERE x IS NOT NULL | x]",
            {
                "uid": uid,
                "canonical": entity.canonical_name or entity.name,
                "name": entity.name,
                "aliases": aliases,
                "confidence": entity.confidence,
                "now": _now_iso(),
            },
        )

    def _write_relation_instance(
        self, session, ri_uid: str, rel, source_uid: str, target_uid: str
    ) -> bool:
        """Create a RelationInstance node and connect source → ri → target.

        Returns True if the relation was created, False if source/target
        nodes were not found.
        """
        result = session.run(
            "MATCH (a {uid: $source_uid}) "
            "MATCH (b {uid: $target_uid}) "
            "MERGE (ri:RelationInstance {uid: $ri_uid}) "
            "ON CREATE SET ri.type = $rel_type, "
            "              ri.source_uid = $source_uid, "
            "              ri.target_uid = $target_uid, "
            "              ri.confidence = $confidence, "
            "              ri.created_at = $now "
            "MERGE (a)-[:OUT_REL]->(ri) "
            "MERGE (ri)-[:TO]->(b) "
            "RETURN ri.uid AS uid",
            {
                "source_uid": source_uid,
                "target_uid": target_uid,
                "ri_uid": ri_uid,
                "rel_type": rel.type,
                "confidence": rel.confidence,
                "now": _now_iso(),
            },
        )
        record = result.single()
        if not record:
            logger.warning(
                "RelationInstance not created: %s -> %s (nodes not found: %s, %s)",
                rel.source, rel.target, source_uid, target_uid,
            )
            return False
        return True

    def _write_evidence(
        self, session, ev_uid: str, ri_uid: str,
        passage: PassageRecord, confidence: float,
        citation_metadata: dict | None = None,
    ):
        """Create an Evidence node linked to RelationInstance and Passage."""
        citation_count = 0
        citation_labels: list[str] = []
        if citation_metadata:
            citation_count = int(citation_metadata.get("citation_count", 0))
            citation_labels = citation_metadata.get("citation_labels", [])
        session.run(
            "MATCH (ri:RelationInstance {uid: $ri_uid}) "
            "MATCH (p:Passage {uid: $pass_uid}) "
            "MERGE (e:Evidence {uid: $ev_uid}) "
            "ON CREATE SET e.confidence = $confidence, "
            "              e.extractor = $extractor, "
            "              e.page_number = $page_number, "
            "              e.passage_uid = $pass_uid, "
            "              e.citation_count = $citation_count, "
            "              e.citation_labels = $citation_labels, "
            "              e.created_at = $now "
            "ON MATCH SET e.citation_count = $citation_count, "
            "             e.citation_labels = $citation_labels "
            "MERGE (e)-[:SUPPORTS]->(ri) "
            "MERGE (e)-[:FROM_PASSAGE]->(p)",
            {
                "ri_uid": ri_uid,
                "pass_uid": passage.passage_id,
                "ev_uid": ev_uid,
                "confidence": confidence,
                "extractor": "llm_gpt4.1",
                "page_number": passage.page_number,
                "citation_count": citation_count,
                "citation_labels": citation_labels,
                "now": _now_iso(),
            },
        )

    def write_sections(self, sections: list[SectionRecord], document_id: str):
        """Write Section nodes and link to Document."""
        with self.db.driver.session() as session:
            self.document_writer.write_sections(session, sections, document_id)

        logger.info(
            "Wrote %d sections for document %s",
            len(sections),
            document_id,
        )

    def write_references(self, references: list[ReferenceRecord], document_id: str):
        """Write ReferenceEntry nodes and link to Document."""
        with self.db.driver.session() as session:
            self.document_writer.write_references(session, references, document_id)

        logger.info(
            "Wrote %d references for document %s",
            len(references),
            document_id,
        )

    def write_inline_citations(
        self,
        citations: list[InlineCitationRecord],
        citation_links: list[CitationLinkRecord],
    ) -> dict:
        """Write InlineCitation nodes and structural citation edges."""
        citations_written = 0
        citation_links_written = 0
        unlinked_citations = 0
        with self.db.driver.session() as session:
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

        logger.info(
            "Inline citation write summary: citations=%d linked_to_passage=%d "
            "missing_passage_links=%d refers_to_links=%d",
            len(citations),
            citations_written,
            unlinked_citations,
            citation_links_written,
        )
        return {
            "citations_written": citations_written,
            "citation_links_written": citation_links_written,
            "unlinked_citations": unlinked_citations,
        }

    def _ensure_section(self, session, section: SectionRecord, document_id: str):
        """MERGE a Section node and link to Document."""
        self.document_writer.ensure_section(session, section, document_id)

    def _find_entity_type(self, extraction: ExtractionResult, canonical_name: str) -> str:
        """Find entity type by canonical_name in the extraction."""
        for entity in extraction.entities:
            c = entity.canonical_name or entity.name
            if c == canonical_name:
                return entity.type
        return "Concept"  # fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
