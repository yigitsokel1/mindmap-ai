class FakeSemanticQueryService:
    def answer(self, request):
        if request.document_id == "cross-doc":
            return {
                "answer": "Transformer appears across multiple papers.",
                "query_intent": "METHOD_USAGE",
                "matched_entities": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
                "evidence": [
                    {
                        "relation_type": "USES",
                        "page": 3,
                        "snippet": "Transformer evidence in paper A.",
                        "section": "Methods",
                        "confidence": 0.9,
                        "related_node_ids": ["n-1", "ri-a"],
                        "document_id": "doc-1",
                        "document_name": "paper_a.pdf",
                    },
                    {
                        "relation_type": "USES",
                        "page": 2,
                        "snippet": "Transformer evidence in paper B.",
                        "section": "Methods",
                        "confidence": 0.88,
                        "related_node_ids": ["n-1", "ri-b"],
                        "document_id": "doc-2",
                        "document_name": "paper_b.pdf",
                    },
                ],
                "related_nodes": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
                "primary_focus_node_id": "n-1",
                "secondary_focus_node_ids": ["ri-a", "ri-b"],
                "focus_seed_ids": ["n-1", "ri-a", "ri-b"],
                "citations": [],
                "explanation": {
                    "why_these_entities": ["canonical match"],
                    "why_this_evidence": ["cross-document canonical linkage"],
                    "reasoning_path": ["question_intent:METHOD_USAGE"],
                    "selected_sections": ["Methods"],
                    "selection_signals": ["canonical_linked_match"],
                },
                "confidence": 0.83,
                "limited_evidence": False,
                "uncertainty_signal": False,
                "uncertainty_reason": None,
                "mode": "semantic_grounded",
            }
        if request.document_id == "empty-evidence":
            return {
                "answer": f"Matched semantic nodes for '{request.question}', but no supporting evidence was found.",
                "query_intent": "SUMMARY",
                "matched_entities": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
                "evidence": [],
                "related_nodes": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
                "primary_focus_node_id": "n-1",
                "secondary_focus_node_ids": [],
                "focus_seed_ids": ["n-1"],
                "citations": [],
                "explanation": {
                    "why_these_entities": ["fallback semantic match"],
                    "why_this_evidence": ["no evidence available"],
                    "reasoning_path": ["question_intent:SUMMARY"],
                    "selected_sections": [],
                    "selection_signals": ["entity_mention_match"],
                },
                "confidence": 0.0,
                "limited_evidence": True,
                "uncertainty_signal": True,
                "uncertainty_reason": "no_evidence",
                "mode": "semantic_grounded",
            }
        return {
            "answer": f"Grounded response for: {request.question}",
            "query_intent": "METHOD_USAGE",
            "matched_entities": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
            "evidence": [
                {
                    "relation_type": "USES",
                    "page": 3,
                    "snippet": "Transformer uses self-attention.",
                    "section": "Methods",
                    "confidence": 0.9,
                    "related_node_ids": ["n-1", "ri-1"],
                    "document_id": "doc-1",
                    "document_name": "paper.pdf",
                    "citation_label": "[12]",
                    "reference_entry_id": "ref-1",
                }
            ],
            "related_nodes": [
                {"id": "n-1", "type": "Method", "display_name": "Transformer"},
            ],
            "primary_focus_node_id": "n-1",
            "secondary_focus_node_ids": ["ri-1", "ref-1"],
            "focus_seed_ids": ["n-1", "ri-1", "ref-1"],
            "citations": [{"label": "[12]", "reference_entry_id": "ref-1", "page": 3, "document_name": "paper.pdf"}],
            "explanation": {
                "why_these_entities": ["entity mention match"],
                "why_this_evidence": ["ranked by citation and relation"],
                "reasoning_path": ["question_intent:METHOD_USAGE"],
                "selected_sections": ["Methods"],
                "selection_signals": ["citation_signal_weighted_by_intent"],
            },
            "confidence": 0.81,
            "limited_evidence": False,
            "uncertainty_signal": False,
            "uncertainty_reason": None,
            "mode": "semantic_grounded",
        }


def test_query_semantic_endpoint_contract(api_client, monkeypatch):
    import backend.app.api.query as query_api

    monkeypatch.setattr(query_api, "SemanticQueryService", FakeSemanticQueryService)
    response = api_client.post(
        "/api/query/semantic",
        json={"question": "What is the relation?", "max_evidence": 3, "include_citations": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "semantic_grounded"
    assert body["query_intent"] == "METHOD_USAGE"
    assert "answer" in body
    assert isinstance(body["evidence"], list)
    assert body["evidence"][0]["relation_type"] == "USES"
    assert body["matched_entities"][0]["display_name"] == "Transformer"
    assert body["explanation"]["why_this_evidence"]
    assert body["explanation"]["reasoning_path"]
    assert "selection_signals" in body["explanation"]
    assert body["related_nodes"][0]["display_name"] == "Transformer"
    assert body["primary_focus_node_id"] == "n-1"
    assert "ri-1" in body["secondary_focus_node_ids"]
    assert "limited_evidence" in body
    assert "uncertainty_signal" in body


def test_query_semantic_endpoint_document_filter_contract(api_client, monkeypatch):
    import backend.app.api.query as query_api

    monkeypatch.setattr(query_api, "SemanticQueryService", FakeSemanticQueryService)
    response = api_client.post(
        "/api/query/semantic",
        json={"question": "Which references are cited?", "document_id": "doc-1", "include_citations": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "semantic_grounded"
    assert body["evidence"][0]["document_id"] == "doc-1"
    assert body["evidence"][0]["reference_entry_id"] == "ref-1"
    assert body["citations"][0]["label"] == "[12]"


def test_query_semantic_endpoint_empty_evidence_branch(api_client, monkeypatch):
    import backend.app.api.query as query_api

    monkeypatch.setattr(query_api, "SemanticQueryService", FakeSemanticQueryService)
    response = api_client.post(
        "/api/query/semantic",
        json={"question": "What evidence supports X?", "document_id": "empty-evidence"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evidence"] == []
    assert "supporting evidence" in body["answer"].lower()


def test_query_semantic_endpoint_citation_backed_chain_contract(api_client, monkeypatch):
    import backend.app.api.query as query_api

    monkeypatch.setattr(query_api, "SemanticQueryService", FakeSemanticQueryService)
    response = api_client.post(
        "/api/query/semantic",
        json={"question": "Which citations support this method?", "include_citations": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["citations"]
    assert body["evidence"][0]["citation_label"] == "[12]"
    assert body["evidence"][0]["reference_entry_id"] == "ref-1"


def test_query_semantic_endpoint_cross_document_entity_discovery(api_client, monkeypatch):
    import backend.app.api.query as query_api

    monkeypatch.setattr(query_api, "SemanticQueryService", FakeSemanticQueryService)
    response = api_client.post(
        "/api/query/semantic",
        json={"question": "Transformer hangi paperlarda geçiyor?", "document_id": "cross-doc"},
    )
    assert response.status_code == 200
    body = response.json()
    docs = {item["document_id"] for item in body["evidence"]}
    assert len(docs) == 2


def test_query_semantic_endpoint_validation(api_client):
    response = api_client.post("/api/query/semantic", json={"question": "", "max_evidence": 0})
    assert response.status_code == 422


def test_query_semantic_endpoint_returns_controlled_500(api_client, monkeypatch):
    import backend.app.api.query as query_api

    class FailingSemanticQueryService:
        def answer(self, request):
            raise query_api.SemanticQueryServiceError("db timeout")

    monkeypatch.setattr(query_api, "SemanticQueryService", FailingSemanticQueryService)
    response = api_client.post("/api/query/semantic", json={"question": "What methods are mentioned in this paper?"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Semantic query processing failed. Please try again."
