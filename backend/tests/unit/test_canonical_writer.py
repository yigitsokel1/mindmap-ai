from backend.app.services.graph.writers.canonical_writer import CanonicalWriter


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
        row = {"uid": params.get("canonical_id") or params.get("entity_uid")} if self._result_row else None
        return FakeResult(row)

    @property
    def queries(self):
        return [q for q, _ in self.calls]


def _canonical_payload(**overrides) -> dict:
    base = dict(
        canonical_id="c-transformer",
        entity_type="Method",
        canonical_name="Transformer",
        normalized_name="transformer",
        aliases=["Transformer architecture"],
        normalized_aliases=["transformer architecture"],
        acronyms=[],
        allow_alias_learning=True,
    )
    return {**base, **overrides}


# ── write_canonical ───────────────────────────────────────────────────────────

def test_write_canonical_returns_merged_status():
    session = FakeSession()
    result = CanonicalWriter().write_canonical(session, _canonical_payload())
    assert result["status"] == "merged"
    assert result["canonical_id"] == "c-transformer"


def test_write_canonical_emits_merge_on_canonical_entity():
    session = FakeSession()
    CanonicalWriter().write_canonical(session, _canonical_payload())
    assert "MERGE (c:CanonicalEntity" in session.queries[0]


def test_write_canonical_passes_aliases_and_normalized_aliases():
    session = FakeSession()
    CanonicalWriter().write_canonical(session, _canonical_payload(
        aliases=["Transformer model", "TF"], normalized_aliases=["transformer model", "tf"]
    ))
    _, params = session.calls[0]
    assert "Transformer model" in params["aliases"]
    assert "transformer model" in params["normalized_aliases"]


def test_write_canonical_deduplicates_aliases():
    session = FakeSession()
    CanonicalWriter().write_canonical(session, _canonical_payload(
        aliases=["BERT", "BERT", "bert"],
    ))
    _, params = session.calls[0]
    assert params["aliases"].count("BERT") == 1


def test_write_canonical_returns_skipped_when_db_row_missing():
    session = FakeSession(result_row=False)
    result = CanonicalWriter().write_canonical(session, _canonical_payload())
    assert result["status"] == "skipped"


def test_write_canonical_passes_allow_alias_learning_flag():
    session = FakeSession()
    CanonicalWriter().write_canonical(session, _canonical_payload(allow_alias_learning=False))
    _, params = session.calls[0]
    assert params["allow_alias_learning"] is False


# ── link_instance ─────────────────────────────────────────────────────────────

def test_link_instance_returns_linked_status():
    session = FakeSession()
    result = CanonicalWriter().link_instance(session, "e-1", "c-transformer")
    assert result["status"] == "linked"
    assert result["canonical_id"] == "c-transformer"


def test_link_instance_emits_instance_of_canonical_edge():
    session = FakeSession()
    CanonicalWriter().link_instance(session, "e-1", "c-1")
    assert "INSTANCE_OF_CANONICAL" in session.queries[0]


def test_link_instance_returns_skipped_when_nodes_not_found():
    session = FakeSession(result_row=False)
    result = CanonicalWriter().link_instance(session, "missing-e", "missing-c")
    assert result["status"] == "skipped"


def test_link_instance_passes_entity_and_canonical_uids():
    session = FakeSession()
    CanonicalWriter().link_instance(session, "e-entity-1", "c-canonical-1")
    _, params = session.calls[0]
    assert params["entity_uid"] == "e-entity-1"
    assert params["canonical_id"] == "c-canonical-1"
