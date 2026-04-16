"""Deterministic canonical entity linker.

Links normalized entities to graph-global CanonicalEntity nodes without using
LLMs or embeddings. Matching is precision-first and type-strict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from backend.app.core.db import Neo4jDatabase
from backend.app.domain.identity import build_entity_uid
from backend.app.schemas.entities import BaseEntity
from backend.app.schemas.extraction import ExtractionResult

LINKABLE_TYPES = {"Concept", "Method", "Dataset", "Metric", "Paper"}
LINK_MIN_CONFIDENCE = 0.8
TOKEN_RE = re.compile(r"[^a-z0-9]+")
ACRONYM_RE = re.compile(r"[A-Z]{2,8}$")


@dataclass(frozen=True)
class LinkDecision:
    canonical_id: str
    matched: bool
    link_reason: str
    link_confidence: float
    created_new: bool
    canonical_name: str
    normalized_name: str
    aliases: list[str]


class EntityLinker:
    """Deterministic linker for canonical entity identity."""

    def __init__(self, db: Neo4jDatabase | None = None) -> None:
        self.db = db or Neo4jDatabase()
        if not self.db.driver:
            self.db.connect()

    def link_extraction(
        self,
        extraction: ExtractionResult,
        name_map: dict[str, str] | None = None,
    ) -> tuple[ExtractionResult, dict[str, str]]:
        """Link entities and return enriched extraction plus updated name_map."""
        updated_map = dict(name_map or {})
        linked_entities: list[BaseEntity] = []

        for entity in extraction.entities:
            decision = self.link_entity(entity)
            updated_map[entity.name] = decision.canonical_name
            updated_map[entity.canonical_name or entity.name] = decision.canonical_name
            for alias in entity.aliases or []:
                updated_map[alias] = decision.canonical_name

            linked_entities.append(
                entity.model_copy(
                    update={
                        "canonical_name": decision.canonical_name,
                        "canonical_id": decision.canonical_id,
                        "canonical_linked": decision.matched,
                        "canonical_link_reason": decision.link_reason,
                        "canonical_link_confidence": round(decision.link_confidence, 3),
                        "canonical_created_new": decision.created_new,
                    }
                )
            )

        return ExtractionResult(entities=linked_entities, relations=extraction.relations), updated_map

    def link_entity(self, entity: BaseEntity) -> LinkDecision:
        """Link one normalized entity to an existing canonical or new canonical."""
        canonical_name = entity.canonical_name or entity.name
        normalized_name = _normalize(canonical_name)
        aliases = [alias for alias in dict.fromkeys(entity.aliases or []) if alias]
        normalized_aliases = {_normalize(alias) for alias in aliases if _normalize(alias)}

        if entity.type not in LINKABLE_TYPES or entity.confidence < LINK_MIN_CONFIDENCE:
            canonical_id = _canonical_id(entity.type, normalized_name)
            return LinkDecision(
                canonical_id=canonical_id,
                matched=False,
                link_reason="new_canonical_low_confidence_or_unsupported_type",
                link_confidence=0.0,
                created_new=True,
                canonical_name=canonical_name,
                normalized_name=normalized_name,
                aliases=aliases,
            )

        candidates = self._load_candidates(
            entity_type=entity.type,
            normalized_name=normalized_name,
            normalized_aliases=sorted(normalized_aliases),
        )
        for candidate in candidates:
            reason, confidence = _score_candidate(
                entity_type=entity.type,
                normalized_name=normalized_name,
                normalized_aliases=normalized_aliases,
                entity_name=entity.name,
                candidate=candidate,
            )
            if reason and confidence >= LINK_MIN_CONFIDENCE:
                return LinkDecision(
                    canonical_id=str(candidate.get("canonical_id")),
                    matched=True,
                    link_reason=reason,
                    link_confidence=confidence,
                    created_new=False,
                    canonical_name=str(candidate.get("canonical_name") or canonical_name),
                    normalized_name=str(candidate.get("normalized_name") or normalized_name),
                    aliases=sorted(set(aliases + list(candidate.get("aliases") or []))),
                )

        canonical_id = _canonical_id(entity.type, normalized_name)
        return LinkDecision(
            canonical_id=canonical_id,
            matched=False,
            link_reason="new_canonical_no_match",
            link_confidence=0.0,
            created_new=True,
            canonical_name=canonical_name,
            normalized_name=normalized_name,
            aliases=aliases,
        )

    def _load_candidates(
        self,
        entity_type: str,
        normalized_name: str,
        normalized_aliases: Sequence[str],
    ) -> list[dict]:
        query = """
        MATCH (c:CanonicalEntity {entity_type: $entity_type})
        WHERE c.normalized_name = $normalized_name
           OR $normalized_name IN coalesce(c.normalized_aliases, [])
           OR any(alias IN $normalized_aliases WHERE alias IN coalesce(c.normalized_aliases, []))
           OR (
                c.entity_type <> 'Paper'
                AND (
                    $normalized_name IN coalesce(c.acronyms, [])
                    OR any(alias IN $normalized_aliases WHERE alias IN coalesce(c.acronyms, []))
                )
           )
        RETURN c.uid AS canonical_id,
               c.entity_type AS entity_type,
               c.canonical_name AS canonical_name,
               c.normalized_name AS normalized_name,
               coalesce(c.aliases, []) AS aliases,
               coalesce(c.normalized_aliases, []) AS normalized_aliases,
               coalesce(c.acronyms, []) AS acronyms
        LIMIT 25
        """
        records, _, _ = self.db.driver.execute_query(  # type: ignore[union-attr]
            query,
            {
                "entity_type": entity_type,
                "normalized_name": normalized_name,
                "normalized_aliases": list(normalized_aliases),
            },
        )
        return [dict(record) for record in records]


def _score_candidate(
    *,
    entity_type: str,
    normalized_name: str,
    normalized_aliases: set[str],
    entity_name: str,
    candidate: dict,
) -> tuple[str | None, float]:
    candidate_type = str(candidate.get("entity_type") or "").strip()
    if candidate_type and candidate_type != entity_type:
        return None, 0.0

    candidate_id = str(candidate.get("canonical_id") or "")
    expected_prefix = f"canonical_{entity_type.lower()}:"
    if candidate_id and not candidate_id.lower().startswith(expected_prefix):
        return None, 0.0

    candidate_normalized = str(candidate.get("normalized_name") or "")
    candidate_aliases = {v for v in candidate.get("normalized_aliases", []) if v}
    candidate_acronyms = {v.lower() for v in candidate.get("acronyms", []) if v}

    if normalized_name and normalized_name == candidate_normalized:
        return "normalized_exact_match", 0.99

    if normalized_name and normalized_name in candidate_aliases:
        return "normalized_alias_match", 0.94

    if normalized_aliases.intersection(candidate_aliases):
        return "normalized_alias_match", 0.9

    normalized_entity_name = _normalize(entity_name)
    if normalized_entity_name in candidate_acronyms or normalized_name in candidate_acronyms:
        return "acronym_expansion_match", 0.86

    if _acronym(entity_name) and _acronym(entity_name).lower() in candidate_acronyms:
        return "acronym_expansion_match", 0.84

    return None, 0.0


def _canonical_id(entity_type: str, normalized_name: str) -> str:
    safe_name = normalized_name or "unknown"
    return build_entity_uid(f"canonical_{entity_type}", safe_name)


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.strip().lower()
    compact = TOKEN_RE.sub(" ", lowered)
    return " ".join(compact.split())


def _acronym(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", value)
    words = [word for word in cleaned.split() if word]
    if not words:
        return ""
    acronym = "".join(word[0].upper() for word in words if word[0].isalnum())
    if ACRONYM_RE.match(acronym):
        return acronym
    return ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_canonical_payload(entity: BaseEntity, decision: LinkDecision) -> dict:
    """Build persistence payload for CanonicalEntity merge/write."""
    alias_values = sorted(set((entity.aliases or []) + decision.aliases + [entity.name, decision.canonical_name]))
    acronyms = sorted(
        set(
            acronym.lower()
            for acronym in [_acronym(entity.name), _acronym(decision.canonical_name)]
            if acronym
        )
    )
    normalized_aliases = sorted(set(_normalize(alias) for alias in alias_values if alias))
    return {
        "canonical_id": decision.canonical_id,
        "entity_type": entity.type,
        "canonical_name": decision.canonical_name,
        "normalized_name": decision.normalized_name,
        "aliases": alias_values,
        "normalized_aliases": normalized_aliases,
        "acronyms": acronyms,
        "link_reason": decision.link_reason,
        "link_confidence": decision.link_confidence,
        "created_at": now_iso(),
    }


def iter_linkable_entities(entities: Iterable[BaseEntity]) -> list[BaseEntity]:
    return [entity for entity in entities if entity.type in LINKABLE_TYPES]
