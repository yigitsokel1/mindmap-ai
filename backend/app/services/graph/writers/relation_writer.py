"""Relation and evidence writer for semantic graph persistence."""

import logging
from datetime import datetime, timezone

from backend.app.schemas.extraction import ExtractionResult
from backend.app.schemas.passage import PassageRecord

logger = logging.getLogger(__name__)


class RelationWriter:
    """Persists relation instances and evidence nodes."""

    def write_relation_instance(
        self,
        session,
        ri_uid: str,
        rel,
        source_uid: str,
        target_uid: str,
    ) -> dict:
        """Write a relation instance and return normalized status."""
        result = session.run(
            "MATCH (a {uid: $source_uid}) "
            "MATCH (b {uid: $target_uid}) "
            "MERGE (ri:RelationInstance {uid: $ri_uid}) "
            "ON CREATE SET ri.type = $rel_type, "
            "              ri.source_uid = $source_uid, "
            "              ri.target_uid = $target_uid, "
            "              ri.confidence = $confidence, "
            "              ri.created_at = $now "
            "ON MATCH SET ri.confidence = $confidence "
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
        if not result.single():
            logger.warning(
                "RelationInstance not created: %s -> %s (nodes not found: %s, %s)",
                rel.source,
                rel.target,
                source_uid,
                target_uid,
            )
            return {"status": "skipped", "ri_uid": ri_uid}
        return {"status": "merged", "ri_uid": ri_uid}

    def write_evidence(
        self,
        session,
        ri_uid: str,
        passage: PassageRecord,
        confidence: float,
        evidence_uid: str | None = None,
        citation_metadata: dict | None = None,
    ) -> dict:
        """Write evidence node and relation edges with a normalized result."""
        ev_uid = evidence_uid or f"ev:{ri_uid}:{passage.passage_id}"
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
            "             e.citation_labels = $citation_labels, "
            "             e.confidence = $confidence "
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
        return {"status": "merged", "ev_uid": ev_uid}

    def find_entity_type(self, extraction: ExtractionResult, canonical_name: str) -> str:
        """Find an entity type by canonical name from extraction payload."""
        for entity in extraction.entities:
            candidate_name = entity.canonical_name or entity.name
            if candidate_name == canonical_name:
                return entity.type
        return "Concept"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
