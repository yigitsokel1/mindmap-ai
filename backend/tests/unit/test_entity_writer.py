from backend.app.services.graph.writers.entity_writer import EntityWriter


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
        return FakeResult(self._result_row)


class FakeEntity:
    def __init__(self, type_="Method", name="Transformer", canonical_name="Transformer", confidence=0.9, aliases=None):
        self.type = type_
        self.name = name
        self.canonical_name = canonical_name
        self.confidence = confidence
        self.aliases = aliases or []


# ── write_entity: merged path ─────────────────────────────────────────────────

def test_write_entity_returns_merged_status_on_success():
    session = FakeSession(result_row={"uid": "e-1"})
    result = EntityWriter().write_entity(session, FakeEntity(), uid="e-1")
    assert result["status"] == "merged"
    assert result["uid"] == "e-1"
    assert result["entity_type"] == "Method"


def test_write_entity_emits_merge_with_correct_label():
    session = FakeSession()
    EntityWriter().write_entity(session, FakeEntity(type_="Concept", name="Attention"), uid="e-2")
    query, params = session.calls[0]
    assert "MERGE (e:Concept" in query
    assert params["name"] == "Attention"
    assert params["uid"] == "e-2"


def test_write_entity_uses_canonical_name_if_set():
    session = FakeSession()
    entity = FakeEntity(name="attn mech", canonical_name="Attention Mechanism")
    EntityWriter().write_entity(session, entity, uid="e-3")
    _, params = session.calls[0]
    assert params["canonical"] == "Attention Mechanism"


def test_write_entity_falls_back_to_name_when_no_canonical():
    session = FakeSession()
    entity = FakeEntity(name="Transformer", canonical_name=None)
    EntityWriter().write_entity(session, entity, uid="e-4")
    _, params = session.calls[0]
    assert params["canonical"] == "Transformer"


def test_write_entity_includes_aliases():
    session = FakeSession()
    entity = FakeEntity(aliases=["BERT-style", "Multi-head attn"])
    EntityWriter().write_entity(session, entity, uid="e-5")
    _, params = session.calls[0]
    assert "BERT-style" in params["aliases"]


def test_write_entity_returns_skipped_when_db_returns_no_row():
    session = FakeSession(result_row=None)
    result = EntityWriter().write_entity(session, FakeEntity(), uid="e-6")
    assert result["status"] == "skipped"


def test_write_entity_passes_confidence():
    session = FakeSession()
    EntityWriter().write_entity(session, FakeEntity(confidence=0.75), uid="e-7")
    _, params = session.calls[0]
    assert params["confidence"] == 0.75
