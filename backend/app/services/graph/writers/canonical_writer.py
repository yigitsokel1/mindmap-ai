"""Canonical entity persistence writer."""

from datetime import datetime, timezone


class CanonicalWriter:
    """Persists CanonicalEntity nodes and local-to-canonical links."""

    def write_canonical(self, session, payload: dict) -> dict:
        aliases = _dedupe_strings(payload.get("aliases", []))
        normalized_aliases = _dedupe_strings(payload.get("normalized_aliases", []))
        acronyms = _dedupe_strings(payload.get("acronyms", []))
        allow_alias_learning = bool(payload.get("allow_alias_learning", False))
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
            "ON MATCH SET c.aliases = CASE "
            "               WHEN $allow_alias_learning "
            "               THEN reduce(acc = [], x IN [v IN coalesce(c.aliases, []) + $aliases WHERE v IS NOT NULL] | CASE WHEN x IN acc THEN acc ELSE acc + x END) "
            "               ELSE coalesce(c.aliases, []) "
            "             END, "
            "             c.normalized_aliases = CASE "
            "               WHEN $allow_alias_learning "
            "               THEN reduce(acc = [], x IN [v IN coalesce(c.normalized_aliases, []) + $normalized_aliases WHERE v IS NOT NULL] | CASE WHEN x IN acc THEN acc ELSE acc + x END) "
            "               ELSE coalesce(c.normalized_aliases, []) "
            "             END, "
            "             c.acronyms = reduce(acc = [], x IN [v IN coalesce(c.acronyms, []) + $acronyms WHERE v IS NOT NULL] | CASE WHEN x IN acc THEN acc ELSE acc + x END), "
            "             c.updated_at = $now "
            "RETURN c.uid AS uid",
            {
                "canonical_id": payload["canonical_id"],
                "entity_type": payload["entity_type"],
                "canonical_name": payload["canonical_name"],
                "normalized_name": payload["normalized_name"],
                "aliases": aliases,
                "normalized_aliases": normalized_aliases,
                "acronyms": acronyms,
                "allow_alias_learning": allow_alias_learning,
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


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        values.append(item)
    return values
