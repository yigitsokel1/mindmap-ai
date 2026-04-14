from backend.app.schemas.entities import BaseEntity
from backend.app.schemas.extraction import ExtractionResult
from backend.app.services.normalization.entity_normalizer import normalize_entities


def _entity(name: str, entity_type: str = "Method", confidence: float = 0.9, canonical_name: str | None = None):
    return BaseEntity(
        type=entity_type,
        name=name,
        canonical_name=canonical_name,
        aliases=[],
        confidence=confidence,
    )


def test_normalize_entities_strips_determiner_and_generic_suffix_for_method():
    extraction = ExtractionResult(entities=[_entity("the transformer method", "Method")], relations=[])
    normalized, _ = normalize_entities(extraction)
    assert len(normalized.entities) == 1
    assert normalized.entities[0].canonical_name == "Transformer"


def test_normalize_entities_applies_based_suffix_cleanup():
    extraction = ExtractionResult(entities=[_entity("Graph-based model", "Concept")], relations=[])
    normalized, _ = normalize_entities(extraction)
    assert normalized.entities[0].canonical_name == "Graph"


def test_normalize_entities_drops_low_confidence_and_stop_name():
    extraction = ExtractionResult(
        entities=[
            _entity("this method", "Method", confidence=0.95),
            _entity("transformer", "Method", confidence=0.4),
            _entity("attention", "Concept", confidence=0.9),
        ],
        relations=[],
    )
    normalized, _ = normalize_entities(extraction)
    assert [item.canonical_name for item in normalized.entities] == ["Attention"]


def test_normalize_entities_merges_duplicates_and_keeps_highest_confidence():
    extraction = ExtractionResult(
        entities=[
            _entity("transformer method", "Method", confidence=0.7),
            _entity("Transformer", "Method", confidence=0.95),
        ],
        relations=[],
    )
    normalized, _ = normalize_entities(extraction)
    assert len(normalized.entities) == 1
    winner = normalized.entities[0]
    assert winner.canonical_name == "Transformer"
    assert winner.confidence == 0.95


def test_normalize_entities_non_aggressive_type_keeps_suffix():
    extraction = ExtractionResult(entities=[_entity("The benchmark dataset", "Dataset")], relations=[])
    normalized, _ = normalize_entities(extraction)
    assert normalized.entities[0].canonical_name == "The benchmark dataset"
