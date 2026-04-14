"""Relation normalization layer.

Validates and filters relations after entity normalization.
Ensures relations reference valid entities and conform to
the ontology's type constraints.
"""

import logging

from backend.app.schemas.extraction import ExtractionResult
from backend.app.schemas.relations import Relation

logger = logging.getLogger(__name__)

# Valid (source_type, relation_type, target_type) triples.
# Relations not matching any triple are dropped.
VALID_RELATION_TRIPLES = {
    # Document-level relations (source is __DOCUMENT__ or resolved to entity)
    ("Method", "USES", "Concept"),
    ("Method", "USES", "Method"),
    ("Method", "USES", "Dataset"),
    ("Method", "EVALUATED_ON", "Task"),
    ("Method", "EVALUATED_ON", "Dataset"),
    ("Task", "MEASURED_BY", "Metric"),
    ("Author", "WROTE", "Document"),
    ("Author", "AFFILIATED_WITH", "Institution"),
    ("Document", "MENTIONS", "Concept"),
    ("Document", "MENTIONS", "Method"),
    ("Document", "MENTIONS", "Dataset"),
    ("Document", "MENTIONS", "Task"),
    ("Document", "MENTIONS", "Metric"),
    ("Document", "INTRODUCES", "Method"),
    ("Document", "INTRODUCES", "Concept"),
    ("Document", "ABOUT", "Task"),
    # Cross-entity relations the LLM might produce
    ("Concept", "USES", "Concept"),
    ("Method", "INTRODUCES", "Concept"),
    ("Dataset", "ABOUT", "Task"),
}


def normalize_relations(
    extraction: ExtractionResult,
    name_map: dict[str, str],
) -> ExtractionResult:
    """Normalize relations using the entity name map.

    - Resolves source/target to canonical names via name_map
    - Drops self-loops
    - Drops relations referencing unknown entities
    - Drops relations with invalid type-domain combinations
    - Passes through __DOCUMENT__ as a valid source

    Args:
        extraction: ExtractionResult with normalized entities.
        name_map: Mapping from original entity names to canonical names.

    Returns:
        ExtractionResult with normalized relations.
    """
    # Build lookup: canonical_name -> entity type
    entity_type_by_canonical: dict[str, str] = {}
    for entity in extraction.entities:
        canonical = entity.canonical_name or entity.name
        entity_type_by_canonical[canonical] = entity.type

    normalized: list[Relation] = []

    for rel in extraction.relations:
        # Resolve source
        source_canonical = _resolve_name(rel.source, name_map)
        if source_canonical is None:
            logger.debug(
                "Dropping relation %s: source '%s' not found in entities",
                rel.type,
                rel.source,
            )
            continue

        # Resolve target
        target_canonical = _resolve_name(rel.target, name_map)
        if target_canonical is None:
            logger.debug(
                "Dropping relation %s: target '%s' not found in entities",
                rel.type,
                rel.target,
            )
            continue

        # Drop self-loops
        if source_canonical == target_canonical:
            logger.debug("Dropping self-loop: %s -[%s]-> %s", source_canonical, rel.type, target_canonical)
            continue

        # Type-domain validation
        source_type = entity_type_by_canonical.get(source_canonical, "Document")
        target_type = entity_type_by_canonical.get(target_canonical, "Unknown")

        triple = (source_type, rel.type, target_type)
        if triple not in VALID_RELATION_TRIPLES:
            logger.debug(
                "Dropping invalid relation triple: %s(%s) -[%s]-> %s(%s)",
                source_canonical, source_type, rel.type, target_canonical, target_type,
            )
            continue

        normalized.append(
            rel.model_copy(update={"source": source_canonical, "target": target_canonical})
        )

    logger.info(
        "Relation normalization: %d → %d (dropped %d)",
        len(extraction.relations),
        len(normalized),
        len(extraction.relations) - len(normalized),
    )

    return ExtractionResult(entities=extraction.entities, relations=normalized)


def _resolve_name(name: str, name_map: dict[str, str]) -> str | None:
    """Resolve an entity name to its canonical form.

    Tries exact match first, then case-insensitive match.
    Returns None if the name cannot be resolved.
    """
    # Direct match
    if name in name_map:
        return name_map[name]

    # Case-insensitive match
    name_lower = name.lower()
    for original, canonical in name_map.items():
        if original.lower() == name_lower:
            return canonical

    return None
