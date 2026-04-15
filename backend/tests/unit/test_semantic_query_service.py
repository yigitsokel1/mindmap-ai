from backend.app.schemas.semantic_query import SemanticQueryRequest
from backend.app.services.query.semantic_query_service import SemanticQueryService


class FakeNode:
    def __init__(self, element_id: str, labels: list[str], props: dict):
        self.element_id = element_id
        self.labels = labels
        self._props = props

    def get(self, key, default=None):
        return self._props.get(key, default)


class FakeRel:
    def __init__(self, rel_type: str):
        self.type = rel_type


class FakeDriver:
    def __init__(self):
        self.last_params = None
        self.last_query = ""

    def execute_query(self, query, params=None, database_=None):
        params = params or {}
        self.last_query = query
        self.last_params = params
        if "RETURN DISTINCT n" in query:
            return (
                [
                    {"n": FakeNode("n-1", ["Method"], {"display_name": "Transformer"})},
                    {"n": FakeNode("n-2", ["Concept"], {"display_name": "Self-Attention"})},
                ],
                None,
                None,
            )
        if "MATCH (n)-[:OUT_REL]->(ri:RelationInstance)" in query:
            return (
                [
                    {
                        "r": FakeRel("USES"),
                        "ri": FakeNode("ri-1", ["RelationInstance"], {"type": "SUPPORTS_METHOD"}),
                        "ev": FakeNode("ev-1", ["Evidence"], {"statement": "Transformer uses self-attention."}),
                        "p": FakeNode(
                            "p-1",
                            ["Passage"],
                            {"text": "Transformer architecture uses self-attention blocks.", "page_number": 4},
                        ),
                        "d": FakeNode("d-1", ["Document"], {"uid": "doc-1", "name": "paper.pdf"}),
                        "ic": FakeNode("ic-1", ["InlineCitation"], {"reference_labels": ["[12]"]}),
                        "ref": FakeNode("ref-1", ["ReferenceEntry"], {"citation_key_author_year": "Vaswani2017"}),
                    }
                ],
                None,
                None,
            )
        return ([], None, None)


class FakeDB:
    def __init__(self):
        self.driver = FakeDriver()

    def connect(self):
        return None


def test_semantic_query_service_builds_grounded_answer(monkeypatch):
    import backend.app.services.query.semantic_query_service as service_module

    monkeypatch.setattr(service_module, "Neo4jDatabase", FakeDB)
    service = SemanticQueryService()
    result = service.answer(SemanticQueryRequest(question="How is transformer related to self-attention?"))

    assert result.mode == "semantic_grounded"
    assert result.query_intent in {"SUMMARY", "RELATION_LOOKUP"}
    assert "Transformer" in result.answer
    assert len(result.evidence) == 1
    assert result.evidence[0].relation_type == "SUPPORTS_METHOD"
    assert result.evidence[0].page == 4
    assert result.evidence[0].document_id == "doc-1"
    assert result.evidence[0].citation_label == "[12]"
    assert result.evidence[0].reference_entry_id == "ref-1"
    assert len(result.related_nodes) == 2
    assert len(result.matched_entities) == 2
    assert result.explanation.why_these_entities
    assert result.explanation.why_this_evidence
    assert len(result.citations) == 1
    assert result.confidence > 0


def test_semantic_query_service_uses_current_schema_edges(monkeypatch):
    import backend.app.services.query.semantic_query_service as service_module

    fake_db = FakeDB()
    monkeypatch.setattr(service_module, "Neo4jDatabase", lambda: fake_db)
    service = SemanticQueryService()
    service.answer(SemanticQueryRequest(question="what evidence supports transformer?"))

    assert "MATCH (n)-[:OUT_REL]->(ri:RelationInstance)" in fake_db.driver.last_query
    assert "[:SUPPORTS]" in fake_db.driver.last_query
    assert "[:FROM_PASSAGE]" in fake_db.driver.last_query
    assert "[:HAS_SECTION]" in fake_db.driver.last_query
    assert "[:HAS_PASSAGE]" in fake_db.driver.last_query
    assert "[:HAS_INLINE_CITATION]" in fake_db.driver.last_query
    assert "[:REFERS_TO]" in fake_db.driver.last_query


def test_semantic_query_service_document_filter_passed_to_evidence_query(monkeypatch):
    import backend.app.services.query.semantic_query_service as service_module

    fake_db = FakeDB()
    monkeypatch.setattr(service_module, "Neo4jDatabase", lambda: fake_db)
    service = SemanticQueryService()
    service.answer(SemanticQueryRequest(question="transformer", document_id="doc-xyz"))

    assert fake_db.driver.last_params["document_id"] == "doc-xyz"


def test_semantic_query_service_citation_label_fallbacks(monkeypatch):
    import backend.app.services.query.semantic_query_service as service_module

    class CitationFallbackDriver(FakeDriver):
        def execute_query(self, query, params=None, database_=None):
            if "RETURN DISTINCT n" in query:
                return ([{"n": FakeNode("n-1", ["Concept"], {"display_name": "Attention"})}], None, None)
            if "MATCH (n)-[:OUT_REL]->(ri:RelationInstance)" in query:
                return (
                    [
                        {
                            "r": FakeRel("RELATED_TO"),
                            "ri": FakeNode("ri-1", ["RelationInstance"], {"type": "RELATED_TO"}),
                            "ev": FakeNode("ev-1", ["Evidence"], {"page_number": 6}),
                            "p": FakeNode("p-1", ["Passage"], {"text": "Attention description", "page_number": 6}),
                            "d": FakeNode("d-1", ["Document"], {"uid": "doc-1", "name": "paper.pdf"}),
                            "ic": FakeNode("ic-1", ["InlineCitation"], {"raw_text": "(Vaswani et al., 2017)"}),
                            "ref": FakeNode(
                                "ref-1",
                                ["ReferenceEntry"],
                                {"citation_key_numeric": "[12]", "citation_key_author_year": "Vaswani2017"},
                            ),
                        }
                    ],
                    None,
                    None,
                )
            return ([], None, None)

    class CitationFallbackDB(FakeDB):
        def __init__(self):
            self.driver = CitationFallbackDriver()

    monkeypatch.setattr(service_module, "Neo4jDatabase", CitationFallbackDB)
    service = SemanticQueryService()
    result = service.answer(SemanticQueryRequest(question="which citations are used?"))

    assert result.citations[0].label == "(Vaswani et al., 2017)"


def test_semantic_query_service_handles_nodes_without_evidence(monkeypatch):
    import backend.app.services.query.semantic_query_service as service_module

    class NoEvidenceDriver(FakeDriver):
        def execute_query(self, query, params=None, database_=None):
            if "RETURN DISTINCT n" in query:
                return ([{"n": FakeNode("n-1", ["Method"], {"display_name": "Transformer"})}], None, None)
            if "MATCH (n)-[:OUT_REL]->(ri:RelationInstance)" in query:
                return ([{"ri": FakeNode("ri-1", ["RelationInstance"], {"type": "USES"})}], None, None)
            return ([], None, None)

    class NoEvidenceDB(FakeDB):
        def __init__(self):
            self.driver = NoEvidenceDriver()

    monkeypatch.setattr(service_module, "Neo4jDatabase", NoEvidenceDB)
    service = SemanticQueryService()
    result = service.answer(SemanticQueryRequest(question="what evidence supports transformer"))

    assert result.evidence == []
    assert "no supporting evidence" in result.answer.lower()


def test_semantic_query_service_handles_no_matches(monkeypatch):
    import backend.app.services.query.semantic_query_service as service_module

    class EmptyDriver(FakeDriver):
        def execute_query(self, query, params=None, database_=None):
            return ([], None, None)

    class EmptyDB(FakeDB):
        def __init__(self):
            self.driver = EmptyDriver()

    monkeypatch.setattr(service_module, "Neo4jDatabase", EmptyDB)
    service = SemanticQueryService()
    result = service.answer(SemanticQueryRequest(question="zzzz"))

    assert result.answer.startswith("No semantic grounding found")
    assert result.evidence == []
    assert result.related_nodes == []
    assert result.matched_entities == []
    assert result.citations == []
    assert result.confidence == 0
