from backend.app.schemas.citation import CitationLinkRecord, InlineCitationRecord
from backend.app.services.graph.graph_writer import GraphWriter


class FakeResult:
    def __init__(self, row):
        self._row = row

    def single(self):
        return self._row


class FakeSession:
    def __init__(self):
        self.calls = []

    def run(self, query, params):
        self.calls.append((query, params))
        if "MATCH (p:Passage" in query and params.get("passage_uid") == "missing-pass":
            return FakeResult(None)
        return FakeResult({"ok": True})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


class FakeDB:
    def __init__(self, session):
        self.driver = FakeDriver(session)


def test_write_inline_citations_persists_chain_and_counts(monkeypatch):
    import backend.app.services.graph.graph_writer as writer_module

    fake_session = FakeSession()
    monkeypatch.setattr(writer_module, "Neo4jDatabase", lambda: FakeDB(fake_session))

    writer = GraphWriter()
    stats = writer.write_inline_citations(
        citations=[
            InlineCitationRecord(
                citation_id="ic-1",
                document_id="doc-1",
                passage_id="pass-1",
                page_number=1,
                raw_text="[1]",
                citation_style="numeric",
                start_char=0,
                end_char=2,
                reference_keys=["1"],
                reference_labels=[],
            ),
            InlineCitationRecord(
                citation_id="ic-2",
                document_id="doc-1",
                passage_id="missing-pass",
                page_number=1,
                raw_text="[2]",
                citation_style="numeric",
                start_char=3,
                end_char=5,
                reference_keys=["2"],
                reference_labels=[],
            ),
        ],
        citation_links=[
            CitationLinkRecord(
                inline_citation_id="ic-1",
                reference_entry_id="ref-1",
                confidence=1.0,
            )
        ],
    )

    assert stats["citations_written"] == 1
    assert stats["unlinked_citations"] == 1
    assert stats["citation_links_written"] == 1
    assert any("HAS_INLINE_CITATION" in query for query, _ in fake_session.calls)
    assert any("REFERS_TO" in query for query, _ in fake_session.calls)
