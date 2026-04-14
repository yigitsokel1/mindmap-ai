from backend.app.services.extraction.pipeline import PipelineResult


class FakePipeline:
    def run(self, document_id, passages):
        return PipelineResult(
            document_id=document_id,
            pages_total=1,
            passages_total=len(passages),
            passages_succeeded=len(passages),
            passages_failed=0,
            entities_total=2,
            relations_total=1,
            evidence_total=1,
            entities_dropped=0,
            relations_dropped=0,
            errors=[],
        )


def test_extract_endpoint_minimal_text_returns_diagnostics(api_client, monkeypatch):
    import backend.app.api.extract as extract_api

    monkeypatch.setattr(extract_api, "ExtractionPipeline", FakePipeline)
    response = api_client.post("/api/extract", json={"text": "Transformer uses attention.", "document_id": "doc-1"})
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["document_id"] == "doc-1"
    assert body["passages_total"] >= 1
    assert "entities_total" in body
    assert "relations_total" in body
    assert "errors" in body
