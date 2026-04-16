"""Canonical entity persistence writer."""

from datetime import datetime, timezone


class CanonicalWriter:
    """Persists CanonicalEntity nodes and local-to-canonical links."""

    def write_canonical(self, session, payload: dict) -> dict:
        result = session.run(
            "MERGE (c:CanonicalEntity {uid: $canonical_id}) "
            "ON CREATE SET c.entity_type = $entity_type, "
            "             c.canonical_name = $canonical_name, "
            "             c.normalized_name = $normalized_name, "
            "             c.aliases = $aliases, "
            "             c.normalized_aliases = $normalized_aliases, "
            "             c.acronyms = $acronyms, "
            "             c.created_at = $now, "
            "             c.updated_at = $now "
            "ON MATCH SET c.aliases = [x IN coalesce(c.aliases, []) + $aliases WHERE x IS NOT NULL], "
            "             c.normalized_aliases = [x IN coalesce(c.normalized_aliases, []) + $normalized_aliases WHERE x IS NOT NULL], "
            "             c.acronyms = [x IN coalesce(c.acronyms, []) + $acronyms WHERE x IS NOT NULL], "
            "             c.updated_at = $now "
            "RETURN c.uid AS uid",
            {
                "canonical_id": payload["canonical_id"],
                "entity_type": payload["entity_type"],
                "canonical_name": payload["canonical_name"],
                "normalized_name": payload["normalized_name"],
                "aliases": payload.get("aliases", []),
                "normalized_aliases": payload.get("normalized_aliases", []),
                "acronyms": payload.get("acronyms", []),
                "now": _now_iso(),
            },
        )
        return {"status": "merged" if result.single() else "skipped", "canonical_id": payload["canonical_id"]}

    def link_instance(self, session, entity_uid: str, canonical_id: str) -> dict:
        result = session.run(
            "MATCH (e {uid: $entity_uid}) "
            "MATCH (c:CanonicalEntity {uid: $canonical_id}) "
            "MERGE (e)-[:INSTANCE_OF_CANONICAL]->(c) "
            "RETURN c.uid AS canonical_id",
            {"entity_uid": entity_uid, "canonical_id": canonical_id},
        )
        return {"status": "linked" if result.single() else "skipped", "canonical_id": canonical_id}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
