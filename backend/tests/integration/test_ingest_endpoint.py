from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class FakeResult:
    document_id: str = "doc-123"
    file_name: str = "paper.pdf"
    saved_file_name: str = "paper.pdf"
    is_duplicate: bool = False
    status: str = "success"
    pages_total: int = 1
    passages_total: int = 1
    passages_succeeded: int = 1
    passages_failed: int = 0
    entities_written: int = 1
    relations_written: int = 1
    evidence_written: int = 1
    entities_dropped: int = 0
    relations_dropped: int = 0
    sections_total: int = 1
    references_total: int = 1
    reference_entries_total: int = 1
    inline_citations_total: int = 1
    citation_links_total: int = 1
    body_passages_total: int = 1
    reference_passages_skipped: int = 0
    errors: list = None

    def to_dict(self):
        return {
            "document_id": self.document_id,
            "file_name": self.file_name,
            "saved_file_name": self.saved_file_name,
            "is_duplicate": self.is_duplicate,
            "status": self.status,
            "pages_total": self.pages_total,
            "passages_total": self.passages_total,
            "passages_succeeded": self.passages_succeeded,
            "passages_failed": self.passages_failed,
            "entities_written": self.entities_written,
            "relations_written": self.relations_written,
            "evidence_written": self.evidence_written,
            "entities_dropped": self.entities_dropped,
            "relations_dropped": self.relations_dropped,
            "sections_total": self.sections_total,
            "references_total": self.references_total,
            "reference_entries_total": self.reference_entries_total,
            "inline_citations_total": self.inline_citations_total,
            "citation_links_total": self.citation_links_total,
            "body_passages_total": self.body_passages_total,
            "reference_passages_skipped": self.reference_passages_skipped,
            "errors": self.errors or [],
        }


class FakeSemanticIngestionService:
    def ingest_pdf(self, file_path, file_name, progress_callback=None):
        if progress_callback:
            progress_callback("uploaded", {"file_name": file_name})
            progress_callback("parsing")
            progress_callback("detecting_sections")
            progress_callback("parsing_references")
            progress_callback("extracting_semantics")
            progress_callback("writing_graph")
            progress_callback("completed", {"document_id": "doc-123"})
        return FakeResult(file_name=file_name)


def _build_client():
    from backend.app.api.ingest import router as ingest_router

    app = FastAPI()
    app.include_router(ingest_router, prefix="/api")
    return TestClient(app)


def test_ingest_endpoint_returns_job_id_and_status(monkeypatch):
    import backend.app.api.ingest as ingest_api

    monkeypatch.setattr(ingest_api, "SemanticIngestionService", FakeSemanticIngestionService)
    client = _build_client()

    response = client.post(
        "/api/ingest",
        files={"file": ("paper.pdf", b"%PDF-1.4\nfake-content", "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "ingest_job_id" in body
    assert body["document_id"] == "doc-123"

    status_response = client.get(f"/api/ingest/{body['ingest_job_id']}")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == "completed"
    assert status_body["stage"] == "completed"
    assert status_body["document_id"] == "doc-123"


def test_ingest_status_not_found():
    client = _build_client()
    response = client.get("/api/ingest/does-not-exist")
    assert response.status_code == 404
