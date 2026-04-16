"""Entity normalization layer.

Cleans, normalizes, and deduplicates entities before they reach
the graph writer. This is the gate between raw LLM output and
the canonical knowledge graph.
"""

import logging
import re

from backend.app.domain.identity import build_entity_uid
from backend.app.schemas.entities import BaseEntity
from backend.app.schemas.extraction import ExtractionResult
from backend.app.services.normalization.entity_linker import TYPE_MIN_CONFIDENCE

logger = logging.getLogger(__name__)

# Entities shorter than this (after trimming) are dropped
MIN_NAME_LENGTH = 2

# Generic words that are not meaningful entities
STOP_NAMES = {
    "it", "this", "that", "these", "those",
    "the method", "this method", "the model", "this model",
    "the system", "this system", "the approach", "this approach",
    "the paper", "this paper", "our method", "our model",
    "the authors", "the results", "the data",
    "method", "model", "system", "approach", "paper",
    "result", "results", "data", "experiment", "experiments",
    "figure", "table", "section", "chapter",
}

# Fallback threshold for unsupported types.
CONFIDENCE_THRESHOLD = 0.6
AGGRESSIVE_SIMPLIFY_TYPES = {"Method", "Concept"}
LEADING_DETERMINER_RE = re.compile(r"^(?:the|a|an)\s+", flags=re.IGNORECASE)
GENERIC_SUFFIXES = ("model", "method", "approach", "architecture", "system", "framework")


def normalize_name(name: str) -> str:
    """Clean and normalize an entity name.

    - Strip whitespace
    - Collapse repeated whitespace
    - Remove surrounding quotes and parentheses
    - Strip trailing punctuation (except hyphens and parentheses)
    """
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    # Remove surrounding quotes
    if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"'":
        name = name[1:-1].strip()
    # Remove trailing punctuation (keep hyphens, they're part of names)
    name = re.sub(r"[.,;:!?]+$", "", name)
    return name


def build_canonical_name(name: str, entity_type: str | None = None) -> str:
    """Build a canonical name from a normalized name.

    Uses title case with special handling for acronyms and
    hyphenated terms.
    """
    normalized = normalize_name(name)
    normalized = _simplify_name_for_type(normalized, entity_type)
    # If it looks like an acronym (all caps, ≤ 6 chars), keep as-is
    if normalized.isupper() and len(normalized) <= 6:
        return normalized
    # If it contains a hyphen, title-case each part
    if "-" in normalized:
        return "-".join(part.capitalize() for part in normalized.split("-"))
    # Default: title case
    return normalized.title() if normalized.islower() else normalized


def _simplify_name_for_type(name: str, entity_type: str | None) -> str:
    """Apply type-aware canonical simplifications."""
    if entity_type not in AGGRESSIVE_SIMPLIFY_TYPES:
        return name

    simplified = LEADING_DETERMINER_RE.sub("", name).strip()
    if not simplified:
        return name

    suffix_group = "|".join(GENERIC_SUFFIXES)
    based_pattern = re.compile(
        rf"^(.+?)-based\s+(?:{suffix_group})$",
        flags=re.IGNORECASE,
    )
    based_match = based_pattern.match(simplified)
    if based_match:
        simplified = based_match.group(1).strip()

    suffix_pattern = re.compile(rf"\s+(?:{suffix_group})$", flags=re.IGNORECASE)
    while True:
        reduced = suffix_pattern.sub("", simplified).strip()
        if reduced == simplified or not reduced:
            break
        simplified = reduced

    return simplified


def normalize_entities(extraction: ExtractionResult) -> ExtractionResult:
    """Normalize all entities in an extraction result.

    - Cleans names
    - Generates canonical_name if missing
    - Drops entities below confidence threshold
    - Drops stop-word entities
    - Drops too-short entities
    - Deduplicates by canonical_name within the batch
    - Assigns UIDs

    Returns a new ExtractionResult with normalized entities.
    Relations are passed through unchanged (see relation_normalizer).
    """
    seen: dict[str, BaseEntity] = {}  # canonical_name -> entity
    name_map: dict[str, str] = {}  # original name -> canonical_name

    for entity in extraction.entities:
        # Clean name
        clean = normalize_name(entity.name)

        # Drop empty / too short
        if len(clean) < MIN_NAME_LENGTH:
            logger.debug("Dropping short entity: '%s'", entity.name)
            continue

        # Drop stop names
        if clean.lower() in STOP_NAMES:
            logger.debug("Dropping stop entity: '%s'", clean)
            continue

        # Drop low confidence
        type_threshold = TYPE_MIN_CONFIDENCE.get(entity.type, CONFIDENCE_THRESHOLD)
        if entity.confidence < type_threshold:
            logger.debug(
                "Dropping low-confidence entity: '%s' (%.2f)",
                clean,
                entity.confidence,
            )
            continue

        # Build canonical name
        canonical = build_canonical_name(
            entity.canonical_name if entity.canonical_name else clean,
            entity.type,
        )

        # Build UID
        uid = build_entity_uid(entity.type, canonical)

        # Track name mapping for relation source/target resolution
        name_map[entity.name] = canonical
        if entity.canonical_name:
            name_map[entity.canonical_name] = canonical

        # Deduplicate within batch — keep highest confidence
        if uid in seen:
            existing = seen[uid]
            if entity.confidence > existing.confidence:
                seen[uid] = entity.model_copy(
                    update={
                        "name": clean,
                        "canonical_name": canonical,
                        "aliases": list(set(existing.aliases + entity.aliases + [clean])),
                    }
                )
            else:
                # Merge aliases from the duplicate
                merged_aliases = list(set(existing.aliases + [clean]))
                seen[uid] = existing.model_copy(update={"aliases": merged_aliases})
        else:
            seen[uid] = entity.model_copy(
                update={"name": clean, "canonical_name": canonical}
            )

    normalized_entities = list(seen.values())

    logger.info(
        "Entity normalization: %d → %d (dropped %d)",
        len(extraction.entities),
        len(normalized_entities),
        len(extraction.entities) - len(normalized_entities),
    )

    return ExtractionResult(
        entities=normalized_entities,
        relations=extraction.relations,
    ), name_map
