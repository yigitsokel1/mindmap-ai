from backend.app.schemas.document_structure import ReferenceRecord, SectionRecord
from backend.app.schemas.passage import PassageRecord
from backend.app.services.graph.writers.document_writer import DocumentStructureWriter


class FakeResult:
    def __init__(self, row=True):
        self._row = row

    def single(self):
        return self._row


class FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def run(self, query: str, params: dict):
        self.calls.append((query, params))
        return FakeResult()

    @property
    def queries(self) -> list[str]:
        return [q for q, _ in self.calls]

    @property
    def all_params(self) -> list[dict]:
        return [p for _, p in self.calls]


def _make_passage(**kwargs) -> PassageRecord:
    defaults = dict(
        passage_id="p-1",
        document_id="doc-1",
        text="Sample text.",
        index=0,
        page_number=2,
        section_title="Intro",
        section_id=None,
    )
    return PassageRecord(**{**defaults, **kwargs})


def _make_section(**kwargs) -> SectionRecord:
    defaults = dict(
        section_id="s-1",
        document_id="doc-1",
        title="Introduction",
        ordinal=0,
        level=1,
        page_start=1,
        page_end=5,
    )
    return SectionRecord(**{**defaults, **kwargs})


def _make_reference(**kwargs) -> ReferenceRecord:
    defaults = dict(
        reference_id="ref-1",
        document_id="doc-1",
        raw_text="Vaswani et al. 2017",
        order=1,
        year=2017,
        title_guess="Attention Is All You Need",
        authors_guess=["Vaswani"],
        citation_key_numeric=1,
        citation_key_author_year=["Vaswani2017"],
    )
    return ReferenceRecord(**{**defaults, **kwargs})


def _new_writer() -> DocumentStructureWriter:
    return DocumentStructureWriter.__new__(DocumentStructureWriter)


# ── ensure_document ──────────────────────────────────────────────────────────

def test_ensure_document_emits_merge_query():
    session = FakeSession()
    _new_writer().ensure_document(session, "doc-1")
    assert len(session.calls) == 1
    assert "MERGE (d:Document" in session.queries[0]
    assert session.all_params[0]["uid"] == "doc-1"


def test_ensure_document_includes_metadata_fields():
    session = FakeSession()
    _new_writer().ensure_document(
        session,
        "doc-1",
        {"file_name": "paper.pdf", "file_hash": "abc123", "saved_file_name": "paper_abc.pdf"},
    )
    query, params = session.calls[0]
    assert "d.file_name" in query
    assert "d.file_hash" in query
    assert params["file_name"] == "paper.pdf"
    assert params["file_hash"] == "abc123"


def test_ensure_document_no_metadata_excludes_optional_fields():
    session = FakeSession()
    _new_writer().ensure_document(session, "doc-42")
    _, params = session.calls[0]
    assert "file_name" not in params


# ── ensure_passage ────────────────────────────────────────────────────────────

def test_ensure_passage_merges_passage_and_links_document():
    session = FakeSession()
    _new_writer().ensure_passage(session, _make_passage())
    assert any("MERGE (p:Passage" in q for q in session.queries)
    assert any("HAS_PASSAGE" in q for q in session.queries)


def test_ensure_passage_without_section_id_runs_one_query():
    session = FakeSession()
    _new_writer().ensure_passage(session, _make_passage(section_id=None))
    assert len(session.calls) == 1


def test_ensure_passage_with_section_id_links_section():
    session = FakeSession()
    _new_writer().ensure_passage(session, _make_passage(section_id="sec-1"))
    assert len(session.calls) == 2
    second_query = session.queries[1]
    assert "MATCH (s:Section" in second_query
    assert "HAS_PASSAGE" in second_query


# ── write_sections ────────────────────────────────────────────────────────────

def test_write_sections_merges_section_node_and_has_section_link():
    session = FakeSession()
    sections = [_make_section(section_id="s-1"), _make_section(section_id="s-2", title="Methods")]
    _new_writer().write_sections(session, sections, "doc-1")
    assert len(session.calls) == 2
    for q in session.queries:
        assert "MERGE (s:Section" in q
        assert "HAS_SECTION" in q


def test_write_sections_passes_document_id():
    session = FakeSession()
    _new_writer().write_sections(session, [_make_section()], "doc-xyz")
    assert session.all_params[0]["doc_uid"] == "doc-xyz"


# ── write_references ──────────────────────────────────────────────────────────

def test_write_references_merges_reference_entry():
    session = FakeSession()
    _new_writer().write_references(session, [_make_reference()], "doc-1")
    assert len(session.calls) == 1
    assert "MERGE (r:ReferenceEntry" in session.queries[0]
    assert "HAS_REFERENCE" in session.queries[0]


def test_write_references_passes_year_and_keys():
    session = FakeSession()
    _new_writer().write_references(session, [_make_reference(year=2017)], "doc-1")
    params = session.all_params[0]
    assert params["year"] == 2017
    assert params["citation_key_author_year"] == ["Vaswani2017"]


def test_write_multiple_references_runs_one_query_each():
    session = FakeSession()
    refs = [_make_reference(reference_id=f"ref-{i}") for i in range(3)]
    _new_writer().write_references(session, refs, "doc-1")
    assert len(session.calls) == 3


# ── check_duplicate_by_hash ───────────────────────────────────────────────────

def test_check_duplicate_by_hash_returns_uid_when_found(monkeypatch):
    import backend.app.services.graph.writers.document_writer as mod

    class FakeDB:
        def __init__(self):
            self.driver = True

        def connect(self):
            pass

        def execute_query_with_retry(self, query, params=None):
            return ([{"uid": "doc-existing"}], None, None)

    monkeypatch.setattr(mod, "Neo4jDatabase", FakeDB)
    result = DocumentStructureWriter().check_duplicate_by_hash("abc123")
    assert result == "doc-existing"


def test_check_duplicate_by_hash_returns_none_when_not_found(monkeypatch):
    import backend.app.services.graph.writers.document_writer as mod

    class FakeDB:
        def __init__(self):
            self.driver = True

        def connect(self):
            pass

        def execute_query_with_retry(self, query, params=None):
            return ([], None, None)

    monkeypatch.setattr(mod, "Neo4jDatabase", FakeDB)
    assert DocumentStructureWriter().check_duplicate_by_hash("no-match") is None


# ── store_document_metadata ───────────────────────────────────────────────────

def test_store_document_metadata_runs_merge_with_file_fields(monkeypatch):
    import backend.app.services.graph.writers.document_writer as mod

    executed: list[dict] = []

    class FakeDB:
        def __init__(self):
            self.driver = True

        def connect(self):
            pass

        def execute_query_with_retry(self, query, params=None):
            executed.append({"query": query, "params": params})
            return ([], None, None)

    monkeypatch.setattr(mod, "Neo4jDatabase", FakeDB)
    DocumentStructureWriter().store_document_metadata("doc-1", "paper.pdf", "hash123", "paper_hash.pdf")
    assert executed
    assert executed[0]["params"]["file_name"] == "paper.pdf"
    assert executed[0]["params"]["file_hash"] == "hash123"
    assert executed[0]["params"]["saved_name"] == "paper_hash.pdf"
