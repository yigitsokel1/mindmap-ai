from backend.app.schemas.semantic_query import CandidateEntity
from backend.app.services.query.semantic_query_reader import SemanticQueryReader
from backend.app.services.query.traversal_planner import TraversalPlan


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeNode:
    def __init__(self, props=None, labels=None, element_id="node-1"):
        self._props = props or {}
        self.labels = set(labels or ["Concept"])
        self.element_id = element_id

    def get(self, key, default=None):
        return self._props.get(key, default)


class FakeRecord:
    def __init__(self, **data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class FakeDriver:
    def __init__(self, records=None):
        self._records = records or []
        self.query_log: list[str] = []

    def execute_query(self, query, params=None):
        self.query_log.append(query)
        return list(self._records), None, None


class FakeDB:
    def __init__(self, driver):
        self.driver = driver


def _make_reader(records=None) -> tuple[SemanticQueryReader, FakeDriver]:
    driver = FakeDriver(records)
    reader = SemanticQueryReader.__new__(SemanticQueryReader)
    reader.db = FakeDB(driver)
    return reader, driver


def _make_plan(**kwargs) -> TraversalPlan:
    defaults = dict(
        strategy="default",
        relation_directions=["outgoing"],
        prioritize_citations=False,
        max_candidate_nodes=10,
        max_evidence_per_candidate=5,
        max_depth=1,
        relation_whitelist=[],
    )
    return TraversalPlan(**{**defaults, **kwargs})


def _make_candidate(**kwargs) -> CandidateEntity:
    base = dict(
        entity_id="node-1",
        name="Transformer",
        type="Method",
        score=1.0,
        match_reason="token_match",
        source="local",
    )
    return CandidateEntity(**{**base, **kwargs})


# ── find_candidate_entities ───────────────────────────────────────────────────

def test_find_candidate_entities_returns_empty_for_no_tokens():
    reader, _ = _make_reader()
    result = reader.find_candidate_entities([], "doc-1", [])
    assert result == []


def test_find_candidate_entities_returns_candidates_from_records():
    node = FakeNode({"canonical_name": "Transformer", "name": "Transformer"}, ["Method"], "node-1")
    reader, _ = _make_reader([FakeRecord(n=node)])
    result = reader.find_candidate_entities(["transformer"], "doc-1", ["Method"])
    assert len(result) == 1
    assert result[0].name == "Transformer"
    assert result[0].type == "Method"
    assert result[0].entity_id == "node-1"


def test_find_candidate_entities_sets_token_match_reason():
    node = FakeNode({"canonical_name": "BERT"}, ["Method"], "n-bert")
    reader, _ = _make_reader([FakeRecord(n=node)])
    result = reader.find_candidate_entities(["bert"], None, [])
    assert result[0].match_reason == "token_match"
    assert result[0].score == 1.0
    assert result[0].source == "local"


def test_find_candidate_entities_skips_records_with_no_node():
    reader, _ = _make_reader([FakeRecord(n=None)])
    result = reader.find_candidate_entities(["transformer"], None, [])
    assert result == []


def test_find_candidate_entities_uses_name_when_no_canonical_name():
    node = FakeNode({"name": "Attention Mechanism"}, ["Concept"], "n-attn")
    reader, _ = _make_reader([FakeRecord(n=node)])
    result = reader.find_candidate_entities(["attention"], None, [])
    assert result[0].name == "Attention Mechanism"


def test_find_candidate_entities_returns_multiple_candidates():
    nodes = [
        FakeRecord(n=FakeNode({"name": "Transformer"}, ["Method"], f"n-{i}"))
        for i in range(3)
    ]
    reader, _ = _make_reader(nodes)
    result = reader.find_candidate_entities(["transformer"], None, [])
    assert len(result) == 3


# ── collect_evidence ─────────────────────────────────────────────────────────

def test_collect_evidence_returns_empty_for_no_candidates():
    reader, _ = _make_reader()
    result = reader.collect_evidence([], 10, None, _make_plan())
    assert result == []


def test_collect_evidence_returns_evidence_item():
    ri = FakeNode({"type": "USES", "confidence": 0.9}, [], "ri-1")
    ev = FakeNode({"text": "Transformers use self-attention.", "confidence": 0.85}, [], "ev-1")
    p = FakeNode({"text": "Transformers use self-attention.", "page_number": 3}, [], "p-1")
    sec = FakeNode({"title": "Methods"}, [], "sec-1")
    doc = FakeNode({"uid": "doc-1", "file_name": "paper.pdf"}, [], "doc-1")
    record = FakeRecord(n=None, ri=ri, ev=ev, p=p, d=doc, sec=sec, ic=None, ref=None)
    reader, _ = _make_reader([record])
    result = reader.collect_evidence([_make_candidate()], 10, None, _make_plan())
    assert len(result) == 1
    item = result[0]
    assert item.relation_type == "USES"
    assert item.page == 4  # page_number=3 + 1
    assert "self-attention" in item.snippet
    assert item.section == "Methods"
    assert item.confidence == 0.9  # ri.confidence takes priority over ev.confidence


def test_collect_evidence_deduplicates_items():
    ri = FakeNode({"type": "USES"}, [], "ri-1")
    ev = FakeNode({"text": "Same text"}, [], "ev-1")
    p = FakeNode({"text": "Same text", "page_number": 1}, [], "p-1")
    record = FakeRecord(n=None, ri=ri, ev=ev, p=p, d=None, sec=None, ic=None, ref=None)
    reader, _ = _make_reader([record, record])
    result = reader.collect_evidence([_make_candidate()], 10, None, _make_plan())
    assert len(result) == 1


def test_collect_evidence_respects_max_evidence():
    records = []
    for i in range(5):
        ri = FakeNode({"type": "USES"}, [], f"ri-{i}")
        ev = FakeNode({"text": f"text {i}"}, [], f"ev-{i}")
        p = FakeNode({"text": f"text {i}", "page_number": i}, [], f"p-{i}")
        records.append(FakeRecord(n=None, ri=ri, ev=ev, p=p, d=None, sec=None, ic=None, ref=None))
    reader, _ = _make_reader(records)
    result = reader.collect_evidence([_make_candidate()], 2, None, _make_plan())
    assert len(result) == 2


def test_collect_evidence_skips_when_no_relation_instance():
    record = FakeRecord(n=None, ri=None, ev=None, p=None, d=None, sec=None, ic=None, ref=None)
    reader, _ = _make_reader([record])
    result = reader.collect_evidence([_make_candidate()], 10, None, _make_plan())
    assert result == []


def test_collect_evidence_skips_when_both_evidence_and_passage_missing():
    ri = FakeNode({"type": "USES"}, [], "ri-1")
    record = FakeRecord(n=None, ri=ri, ev=None, p=None, d=None, sec=None, ic=None, ref=None)
    reader, _ = _make_reader([record])
    result = reader.collect_evidence([_make_candidate()], 10, None, _make_plan())
    assert result == []


def test_collect_evidence_makes_two_queries_for_depth_two():
    reader, driver = _make_reader([])
    reader.collect_evidence([_make_candidate()], 10, None, _make_plan(max_depth=2))
    assert len(driver.query_log) == 2


def test_collect_evidence_makes_one_query_for_depth_one():
    reader, driver = _make_reader([])
    reader.collect_evidence([_make_candidate()], 10, None, _make_plan(max_depth=1))
    assert len(driver.query_log) == 1


def test_collect_evidence_converts_page_number_to_one_based():
    ri = FakeNode({"type": "USES"}, [], "ri-1")
    ev = FakeNode({"text": "passage text"}, [], "ev-1")
    p = FakeNode({"text": "passage text", "page_number": 0}, [], "p-1")
    record = FakeRecord(n=None, ri=ri, ev=ev, p=p, d=None, sec=None, ic=None, ref=None)
    reader, _ = _make_reader([record])
    result = reader.collect_evidence([_make_candidate()], 10, None, _make_plan())
    assert result[0].page == 1  # 0 + 1


def test_collect_evidence_uses_evidence_text_when_no_passage():
    ri = FakeNode({"type": "APPLIES"}, [], "ri-2")
    ev = FakeNode({"text": "evidence text fallback", "page_number": 5}, [], "ev-2")
    record = FakeRecord(n=None, ri=ri, ev=ev, p=None, d=None, sec=None, ic=None, ref=None)
    reader, _ = _make_reader([record])
    result = reader.collect_evidence([_make_candidate()], 10, None, _make_plan())
    assert len(result) == 1
    assert result[0].snippet == "evidence text fallback"
    assert result[0].page == 6  # 5 + 1


# ── lookup_canonical_candidates ───────────────────────────────────────────────

def test_lookup_canonical_candidates_returns_empty_for_no_tokens():
    reader, _ = _make_reader()
    result = reader.lookup_canonical_candidates([])
    assert result == []


def test_lookup_canonical_candidates_returns_canonical_match():
    entity = FakeNode({"name": "Transformer"}, ["Method"], "e-1")
    canonical = FakeNode({"canonical_name": "Transformer"}, ["CanonicalEntity"], "c-1")
    record = FakeRecord(e=entity, c=canonical, doc_count=3)
    reader, _ = _make_reader([record])
    result = reader.lookup_canonical_candidates(["transformer"])
    assert len(result) == 1
    assert result[0].match_reason == "canonical_linked_match"
    assert result[0].source == "canonical-ready"
    assert result[0].name == "Transformer"
    assert result[0].type == "Method"


def test_lookup_canonical_candidates_score_increases_with_doc_count():
    entity = FakeNode({"name": "BERT"}, ["Method"], "e-1")
    canonical = FakeNode({"canonical_name": "BERT"}, [], "c-1")
    record = FakeRecord(e=entity, c=canonical, doc_count=5)
    reader, _ = _make_reader([record])
    result = reader.lookup_canonical_candidates(["bert"])
    assert result[0].score == 0.8 + 5 * 0.02  # 0.9


def test_lookup_canonical_candidates_score_clamps_to_one():
    entity = FakeNode({"name": "GPT"}, ["Method"], "e-2")
    canonical = FakeNode({"canonical_name": "GPT"}, [], "c-2")
    record = FakeRecord(e=entity, c=canonical, doc_count=100)
    reader, _ = _make_reader([record])
    result = reader.lookup_canonical_candidates(["gpt"])
    assert result[0].score == 1.0


def test_lookup_canonical_candidates_skips_missing_entity_or_canonical():
    record = FakeRecord(e=None, c=None, doc_count=0)
    reader, _ = _make_reader([record])
    result = reader.lookup_canonical_candidates(["transformer"])
    assert result == []


def test_lookup_canonical_candidates_uses_canonical_name_over_entity_name():
    entity = FakeNode({"name": "attn mech"}, ["Concept"], "e-1")
    canonical = FakeNode({"canonical_name": "Attention Mechanism"}, [], "c-1")
    record = FakeRecord(e=entity, c=canonical, doc_count=1)
    reader, _ = _make_reader([record])
    result = reader.lookup_canonical_candidates(["attention"])
    assert result[0].name == "Attention Mechanism"


# ── find_fallback_entities ────────────────────────────────────────────────────

def test_find_fallback_entities_returns_candidates():
    node = FakeNode({"canonical_name": "Self-Attention"}, ["Method"], "n-attn")
    record = FakeRecord(n=node, relation_count=5, evidence_count=3, citation_count=2)
    reader, _ = _make_reader([record])
    result = reader.find_fallback_entities("doc-1", [], "DEFINITION", limit=5)
    assert len(result) == 1
    assert result[0].score == 10.0  # 5 + 3 + 2
    assert result[0].match_reason == "graph_density_fallback"
    assert result[0].source == "local"
    assert result[0].name == "Self-Attention"


def test_find_fallback_entities_returns_empty_when_no_records():
    reader, _ = _make_reader([])
    result = reader.find_fallback_entities(None, [], "DEFINITION", limit=5)
    assert result == []


def test_find_fallback_entities_skips_none_node():
    record = FakeRecord(n=None, relation_count=1, evidence_count=1, citation_count=0)
    reader, _ = _make_reader([record])
    result = reader.find_fallback_entities(None, [], "DEFINITION", limit=5)
    assert result == []


def test_find_fallback_entities_score_is_sum_of_counts():
    node = FakeNode({"name": "BLEU"}, ["Metric"], "n-bleu")
    record = FakeRecord(n=node, relation_count=2, evidence_count=0, citation_count=4)
    reader, _ = _make_reader([record])
    result = reader.find_fallback_entities(None, [], "CITATION_BASIS", limit=5)
    assert result[0].score == 6.0
