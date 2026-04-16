"""Entity writer for semantic graph persistence."""

from datetime import datetime, timezone


class EntityWriter:
    """Persists typed entity nodes."""

    def write_entity(self, session, entity, uid: str) -> dict:
        """MERGE a typed entity node and return a normalized write result."""
        aliases = entity.aliases or []
        result = session.run(
            f"MERGE (e:{entity.type} {{uid: $uid}}) "
            "ON CREATE SET e.canonical_name = $canonical, "
            "             e.name = $name, "
            "             e.aliases = $aliases, "
            "             e.confidence = $confidence, "
            "             e.created_at = $now "
            "ON MATCH SET e.aliases = [x IN e.aliases + $aliases WHERE x IS NOT NULL | x], "
            "             e.confidence = $confidence "
            "RETURN e.uid AS uid",
            {
                "uid": uid,
                "canonical": entity.canonical_name or entity.name,
                "name": entity.name,
                "aliases": aliases,
                "confidence": entity.confidence,
                "now": _now_iso(),
            },
        )
        return {
            "status": "merged" if result.single() else "skipped",
            "uid": uid,
            "entity_type": entity.type,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
