from backend.app.schemas.entities import BaseEntity
from backend.app.schemas.extraction import ExtractionResult
from backend.app.schemas.relations import Relation
from backend.app.services.normalization.relation_normalizer import normalize_relations


def _entity(name: str, entity_type: str):
    return BaseEntity(
        type=entity_type,
        name=name,
        canonical_name=name,
        aliases=[],
        confidence=0.9,
    )


def _rel(rel_type: str, source: str, target: str):
    return Relation(type=rel_type, source=source, target=target, confidence=0.8)


def test_normalize_relations_drops_self_loop():
    extraction = ExtractionResult(
        entities=[_entity("Transformer", "Method")],
        relations=[_rel("USES", "Transformer", "Transformer")],
    )
    result = normalize_relations(extraction, {"Transformer": "Transformer"})
    assert result.relations == []


def test_normalize_relations_drops_dangling_reference():
    extraction = ExtractionResult(
        entities=[_entity("Transformer", "Method")],
        relations=[_rel("USES", "Transformer", "Attention")],
    )
    result = normalize_relations(extraction, {"Transformer": "Transformer"})
    assert result.relations == []


def test_normalize_relations_validates_whitelisted_triple():
    extraction = ExtractionResult(
        entities=[_entity("Transformer", "Method"), _entity("Attention", "Concept")],
        relations=[_rel("USES", "Transformer", "Attention")],
    )
    result = normalize_relations(
        extraction,
        {"Transformer": "Transformer", "Attention": "Attention"},
    )
    assert len(result.relations) == 1
    assert result.relations[0].source == "Transformer"
    assert result.relations[0].target == "Attention"


def test_normalize_relations_rejects_invalid_triple():
    extraction = ExtractionResult(
        entities=[_entity("Transformer", "Method"), _entity("Attention", "Concept")],
        relations=[_rel("EVALUATED_ON", "Transformer", "Attention")],
    )
    result = normalize_relations(
        extraction,
        {"Transformer": "Transformer", "Attention": "Attention"},
    )
    assert result.relations == []


def test_normalize_relations_resolves_case_insensitive_names():
    extraction = ExtractionResult(
        entities=[_entity("Transformer", "Method"), _entity("Attention", "Concept")],
        relations=[_rel("USES", "transformer", "attention")],
    )
    result = normalize_relations(
        extraction,
        {"Transformer": "Transformer", "Attention": "Attention"},
    )
    assert len(result.relations) == 1
