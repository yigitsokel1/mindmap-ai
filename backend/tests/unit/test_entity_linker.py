from backend.app.schemas.entities import BaseEntity
from backend.app.services.normalization.entity_linker import EntityLinker


class FakeDriver:
    def __init__(self, records):
        self.records = records

    def execute_query(self, query, params=None, database_=None):  # noqa: ARG002
        return self.records, None, None


class FakeDB:
    def __init__(self, records):
        self.driver = FakeDriver(records)

    def connect(self):
        return None


def _candidate(
    canonical_id: str,
    canonical_name: str,
    normalized_name: str,
    normalized_aliases=None,
    acronyms=None,
):
    return {
        "canonical_id": canonical_id,
        "canonical_name": canonical_name,
        "normalized_name": normalized_name,
        "aliases": [canonical_name],
        "normalized_aliases": normalized_aliases or [],
        "acronyms": acronyms or [],
    }


def test_exact_canonical_match():
    linker = EntityLinker(db=FakeDB([_candidate("canonical_method:transformer", "Transformer", "transformer")]))
    decision = linker.link_entity(
        BaseEntity(type="Method", name="Transformer", canonical_name="Transformer", aliases=[], confidence=0.95)
    )
    assert decision.matched is True
    assert decision.link_reason == "normalized_exact_match"
    assert decision.created_new is False


def test_alias_match():
    linker = EntityLinker(
        db=FakeDB(
            [
                _candidate(
                    "canonical_method:transformer",
                    "Transformer",
                    "transformer",
                    normalized_aliases=["transformer architecture"],
                )
            ]
        )
    )
    decision = linker.link_entity(
        BaseEntity(
            type="Method",
            name="Transformer Architecture",
            canonical_name="Transformer Architecture",
            aliases=[],
            confidence=0.92,
        )
    )
    assert decision.matched is True
    assert decision.link_reason == "normalized_alias_match"


def test_acronym_match():
    linker = EntityLinker(
        db=FakeDB([_candidate("canonical_method:bert", "Bidirectional Encoder Representations", "bidirectional encoder representations", acronyms=["bert"])])
    )
    decision = linker.link_entity(
        BaseEntity(type="Method", name="BERT", canonical_name="BERT", aliases=[], confidence=0.9)
    )
    assert decision.matched is True
    assert decision.link_reason == "acronym_expansion_match"


def test_type_mismatch_no_link():
    linker = EntityLinker(
        db=FakeDB([_candidate("canonical_dataset:bert", "BERT", "bert")])
    )
    decision = linker.link_entity(
        BaseEntity(type="Method", name="BERT", canonical_name="BERT", aliases=[], confidence=0.9)
    )
    assert decision.matched is False
    assert decision.created_new is True


def test_low_confidence_no_link():
    linker = EntityLinker(db=FakeDB([_candidate("canonical_method:transformer", "Transformer", "transformer")]))
    decision = linker.link_entity(
        BaseEntity(type="Method", name="Transformer", canonical_name="Transformer", aliases=[], confidence=0.65)
    )
    assert decision.matched is False
    assert decision.created_new is True
    assert "low_confidence" in decision.link_reason


def test_new_canonical_creation():
    linker = EntityLinker(db=FakeDB([]))
    decision = linker.link_entity(
        BaseEntity(type="Dataset", name="WMT 2014", canonical_name="WMT 2014", aliases=[], confidence=0.95)
    )
    assert decision.matched is False
    assert decision.created_new is True
    assert decision.canonical_id.startswith("canonical_dataset:")
