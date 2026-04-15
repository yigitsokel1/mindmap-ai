class FakeSemanticQueryService:
    def answer(self, request):
        if request.document_id == "empty-evidence":
            return {
                "answer": f"Matched semantic nodes for '{request.question}', but no supporting evidence was found.",
                "evidence": [],
                "related_nodes": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
                "citations": [],
                "confidence": 0.0,
                "mode": "semantic_grounded",
            }
        return {
            "answer": f"Grounded response for: {request.question}",
            "evidence": [
                {
                    "relation_type": "USES",
                    "page": 3,
                    "snippet": "Transformer uses self-attention.",
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
            "citations": [{"label": "[12]", "reference_entry_id": "ref-1", "page": 3, "document_name": "paper.pdf"}],
            "confidence": 0.81,
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
    assert "answer" in body
    assert isinstance(body["evidence"], list)
    assert body["evidence"][0]["relation_type"] == "USES"
    assert body["related_nodes"][0]["display_name"] == "Transformer"


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


def test_query_semantic_endpoint_validation(api_client):
    response = api_client.post("/api/query/semantic", json={"question": "", "max_evidence": 0})
    assert response.status_code == 422
