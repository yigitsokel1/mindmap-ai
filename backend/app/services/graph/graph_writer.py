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

from backend.app.core.db import Neo4jDatabase
from backend.app.domain.identity import build_entity_uid, build_relation_instance_uid
from backend.app.schemas.citation import CitationLinkRecord, InlineCitationRecord
from backend.app.schemas.document_structure import ReferenceRecord, SectionRecord
from backend.app.schemas.extraction import ExtractionResult
from backend.app.schemas.passage import PassageRecord
from backend.app.services.graph.writers.citation_writer import CitationWriter
from backend.app.services.graph.writers.canonical_writer import CanonicalWriter
from backend.app.services.graph.writers.document_writer import DocumentStructureWriter
from backend.app.services.graph.writers.entity_writer import EntityWriter
from backend.app.services.graph.writers.relation_writer import RelationWriter
from backend.app.services.normalization.entity_linker import LinkDecision, build_canonical_payload
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
        self.entity_writer = EntityWriter()
        self.canonical_writer = CanonicalWriter()
        self.relation_writer = RelationWriter()
        self.citation_writer = CitationWriter()

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
            self.document_writer.ensure_document(session, passage.document_id, document_metadata)
            self.document_writer.ensure_passage(session, passage)

            # --- Semantic entity writes ---
            for entity in extraction.entities:
                if entity.type not in ENTITY_LABELS:
                    continue
                canonical = entity.canonical_name or entity.name
                uid = build_entity_uid(entity.type, canonical)
                write_result = self.entity_writer.write_entity(session, entity, uid)
                if write_result["status"] != "skipped":
                    entity_count += 1
                self._write_canonical_link(session, entity, uid)

            # --- Relation + Evidence writes ---
            for rel in extraction.relations:
                source_uid = build_entity_uid(
                    self.relation_writer.find_entity_type(extraction, rel.source),
                    rel.source,
                )
                target_uid = build_entity_uid(
                    self.relation_writer.find_entity_type(extraction, rel.target),
                    rel.target,
                )

                ri_uid = build_relation_instance_uid(rel.type, source_uid, target_uid)
                relation_result = self.relation_writer.write_relation_instance(
                    session, ri_uid, rel, source_uid, target_uid
                )
                if relation_result["status"] != "skipped":
                    relation_count += 1
                    evidence_result = self.relation_writer.write_evidence(
                        session,
                        ri_uid,
                        passage,
                        rel.confidence,
                        citation_metadata=citation_metadata,
                    )
                    if evidence_result["status"] != "skipped":
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
                        self.document_writer.ensure_document(session, passage.document_id, None)
                        self.document_writer.ensure_passage(session, passage)
                        for entity in extraction.entities:
                            if entity.type not in ENTITY_LABELS:
                                continue
                            canonical = entity.canonical_name or entity.name
                            uid = build_entity_uid(entity.type, canonical)
                            write_result = self.entity_writer.write_entity(session, entity, uid)
                            if write_result["status"] != "skipped":
                                entities_written += 1
                            self._write_canonical_link(session, entity, uid)
                        for rel in extraction.relations:
                            source_uid = build_entity_uid(
                                self.relation_writer.find_entity_type(extraction, rel.source),
                                rel.source,
                            )
                            target_uid = build_entity_uid(
                                self.relation_writer.find_entity_type(extraction, rel.target),
                                rel.target,
                            )
                            ri_uid = build_relation_instance_uid(rel.type, source_uid, target_uid)
                            relation_result = self.relation_writer.write_relation_instance(
                                session, ri_uid, rel, source_uid, target_uid
                            )
                            if relation_result["status"] != "skipped":
                                relations_written += 1
                                evidence_result = self.relation_writer.write_evidence(
                                    session,
                                    ri_uid,
                                    passage,
                                    rel.confidence,
                                    citation_metadata=citation_metadata,
                                )
                                if evidence_result["status"] != "skipped":
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

    def _write_canonical_link(self, session, entity, entity_uid: str) -> None:
        canonical_id = entity.canonical_id
        if not canonical_id:
            fallback_name = entity.canonical_name or entity.name
            canonical_id = build_entity_uid(f"canonical_{entity.type}", fallback_name)
        decision = LinkDecision(
            canonical_id=canonical_id,
            matched=bool(entity.canonical_linked),
            link_reason=entity.canonical_link_reason or "writer_fallback",
            link_confidence=float(entity.canonical_link_confidence or 0.0),
            created_new=bool(entity.canonical_created_new),
            canonical_name=entity.canonical_name or entity.name,
            normalized_name=(entity.canonical_name or entity.name).lower(),
            aliases=entity.aliases or [],
        )
        payload = build_canonical_payload(entity, decision)
        self.canonical_writer.write_canonical(session, payload)
        self.canonical_writer.link_instance(session, entity_uid=entity_uid, canonical_id=canonical_id)

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
        with self.db.driver.session() as session:
            write_result = self.citation_writer.write_inline_citations(
                session,
                citations,
                citation_links,
            )

        logger.info(
            "Inline citation write summary: citations=%d linked_to_passage=%d "
            "missing_passage_links=%d refers_to_links=%d",
            len(citations),
            write_result["citations_written"],
            write_result["unlinked_citations"],
            write_result["citation_links_written"],
        )
        return write_result
