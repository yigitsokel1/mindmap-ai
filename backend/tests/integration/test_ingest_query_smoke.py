from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.ingest import router as ingest_router
from backend.app.api.query import router as query_router


@dataclass
class FakeIngestResult:
    document_id: str = "doc-smoke-1"
    file_name: str = "smoke.pdf"
    saved_file_name: str = "smoke.pdf"
    status: str = "success"

    def to_dict(self):
        return {
            "document_id": self.document_id,
            "file_name": self.file_name,
            "saved_file_name": self.saved_file_name,
            "status": self.status,
        }


class FakeSemanticIngestionService:
    def ingest_pdf(self, file_path, file_name, progress_callback=None):
        if progress_callback:
            progress_callback("uploaded")
            progress_callback("parsing")
            progress_callback("completed", {"document_id": "doc-smoke-1"})
        return FakeIngestResult(file_name=file_name)


class FakeSemanticQueryService:
    def answer(self, request):
        return {
            "answer": "Grounded response",
            "query_intent": "CITATION_BASIS",
            "matched_entities": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
            "evidence": [
                {
                    "relation_type": "SUPPORTS_METHOD",
                    "page": 7,
                    "snippet": "Evidence snippet",
                    "section": "Methods",
                    "confidence": 0.88,
                    "related_node_ids": ["n-1", "ri-1"],
                    "document_id": request.document_id,
                    "document_name": "smoke.pdf",
                    "citation_label": "[5]",
                    "reference_entry_id": "ref-5",
                }
            ],
            "related_nodes": [{"id": "n-1", "type": "Method", "display_name": "Transformer"}],
            "citations": [{"label": "[5]", "reference_entry_id": "ref-5", "page": 7, "document_name": "smoke.pdf"}],
            "explanation": {
                "why_these_entities": ["matched transformer token"],
                "why_this_evidence": ["citation chain match"],
            },
            "confidence": 0.82,
            "mode": "semantic_grounded",
        }


def _build_client():
    app = FastAPI()
    app.include_router(ingest_router, prefix="/api")
    app.include_router(query_router, prefix="/api")
    return TestClient(app)


def test_semantic_ingest_to_query_smoke(api_client, monkeypatch):
    import backend.app.api.ingest as ingest_api
    import backend.app.api.query as query_api

    monkeypatch.setattr(ingest_api, "SemanticIngestionService", FakeSemanticIngestionService)
    monkeypatch.setattr(query_api, "SemanticQueryService", FakeSemanticQueryService)
    client = _build_client()

    ingest_response = client.post(
        "/api/ingest",
        files={"file": ("smoke.pdf", b"%PDF-1.4\nsmoke", "application/pdf")},
    )
    assert ingest_response.status_code == 200
    document_id = ingest_response.json()["document_id"]

    query_response = client.post(
        "/api/query/semantic",
        json={
            "question": "Which references support the method?",
            "document_id": document_id,
            "include_citations": True,
        },
    )
    assert query_response.status_code == 200
    body = query_response.json()
    assert body["answer"]
    assert body["evidence"]
    assert body["evidence"][0]["reference_entry_id"] == "ref-5"
    assert body["citations"][0]["reference_entry_id"] == "ref-5"
