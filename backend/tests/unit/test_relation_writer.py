from backend.app.schemas.passage import PassageRecord
from backend.app.services.graph.writers.relation_writer import RelationWriter


class FakeResult:
    def __init__(self, row):
        self._row = row

    def single(self):
        return self._row


class FakeSession:
    def __init__(self, result_row=True):
        self._result_row = result_row
        self.calls: list[tuple[str, dict]] = []

    def run(self, query: str, params: dict):
        self.calls.append((query, params))
        return FakeResult(self._result_row if self._result_row is not True else {"uid": "ok"})

    @property
    def queries(self):
        return [q for q, _ in self.calls]


class FakeRelation:
    def __init__(self, type_="USES", confidence=0.9):
        self.type = type_
        self.confidence = confidence
        self.source = "entity-a"
        self.target = "entity-b"


def _make_passage(**kwargs) -> PassageRecord:
    defaults = dict(
        passage_id="p-1",
        document_id="doc-1",
        text="Transformer architecture uses self-attention.",
        index=0,
        page_number=3,
        section_title="Methods",
    )
    return PassageRecord(**{**defaults, **kwargs})


# ── write_relation_instance ───────────────────────────────────────────────────

def test_write_relation_instance_returns_merged():
    session = FakeSession(result_row={"uid": "ri-1"})
    result = RelationWriter().write_relation_instance(session, "ri-1", FakeRelation(), "src-uid", "tgt-uid")
    assert result["status"] == "merged"
    assert result["ri_uid"] == "ri-1"


def test_write_relation_instance_emits_reified_pattern():
    session = FakeSession()
    RelationWriter().write_relation_instance(session, "ri-1", FakeRelation(), "src-uid", "tgt-uid")
    query = session.queries[0]
    assert "OUT_REL" in query
    assert ":TO" in query
    assert "RelationInstance" in query


def test_write_relation_instance_passes_source_and_target_uids():
    session = FakeSession()
    RelationWriter().write_relation_instance(session, "ri-1", FakeRelation(), "e-src", "e-tgt")
    _, params = session.calls[0]
    assert params["source_uid"] == "e-src"
    assert params["target_uid"] == "e-tgt"


def test_write_relation_instance_returns_skipped_when_nodes_not_found():
    session = FakeSession(result_row=None)
    result = RelationWriter().write_relation_instance(session, "ri-2", FakeRelation(), "missing-a", "missing-b")
    assert result["status"] == "skipped"
    assert result["ri_uid"] == "ri-2"


# ── write_evidence ────────────────────────────────────────────────────────────

def test_write_evidence_returns_merged_with_generated_uid():
    session = FakeSession()
    result = RelationWriter().write_evidence(session, "ri-1", _make_passage(), confidence=0.85)
    assert result["status"] == "merged"
    assert "ri-1" in result["ev_uid"]
    assert "p-1" in result["ev_uid"]


def test_write_evidence_uses_provided_uid():
    session = FakeSession()
    result = RelationWriter().write_evidence(session, "ri-1", _make_passage(), 0.9, evidence_uid="ev-custom")
    assert result["ev_uid"] == "ev-custom"


def test_write_evidence_emits_supports_and_from_passage():
    session = FakeSession()
    RelationWriter().write_evidence(session, "ri-1", _make_passage(), 0.9)
    query = session.queries[0]
    assert "SUPPORTS" in query
    assert "FROM_PASSAGE" in query


def test_write_evidence_includes_citation_metadata():
    session = FakeSession()
    RelationWriter().write_evidence(
        session, "ri-1", _make_passage(), 0.8,
        citation_metadata={"citation_count": 3, "citation_labels": ["[1]", "[2]", "[3]"]},
    )
    _, params = session.calls[0]
    assert params["citation_count"] == 3
    assert "[1]" in params["citation_labels"]


def test_write_evidence_defaults_citation_count_to_zero():
    session = FakeSession()
    RelationWriter().write_evidence(session, "ri-1", _make_passage(), 0.8)
    _, params = session.calls[0]
    assert params["citation_count"] == 0
    assert params["citation_labels"] == []


# ── find_entity_type ──────────────────────────────────────────────────────────

def test_find_entity_type_returns_type_for_matching_canonical_name():
    class Ent:
        def __init__(self, name, canonical, type_):
            self.name = name
            self.canonical_name = canonical
            self.type = type_

    class FakeExtraction:
        pass

    extraction = FakeExtraction()
    extraction.entities = [  # type: ignore[attr-defined]
        Ent("Transformer", "Transformer", "Method"),
        Ent("BLEU", "BLEU Score", "Metric"),
    ]
    assert RelationWriter().find_entity_type(extraction, "Transformer") == "Method"
    assert RelationWriter().find_entity_type(extraction, "BLEU Score") == "Metric"


def test_find_entity_type_falls_back_to_concept_when_not_found():
    class FakeExtraction:
        entities: list = []

    assert RelationWriter().find_entity_type(FakeExtraction(), "Unknown") == "Concept"
