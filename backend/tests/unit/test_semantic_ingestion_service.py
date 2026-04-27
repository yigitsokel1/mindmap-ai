import tempfile
from pathlib import Path

import pytest

from backend.app.services.ingestion.semantic_ingestion_service import (
    IngestionResult,
    SemanticIngestionService,
)


def test_ingest_pdf_raises_when_source_file_missing():
    service = object.__new__(SemanticIngestionService)

    with pytest.raises(FileNotFoundError):
        service.ingest_pdf("D:/not-found.pdf", "not-found.pdf")


def test_ingest_pdf_returns_duplicate_without_running_pipeline(monkeypatch, tmp_path):
    service = object.__new__(SemanticIngestionService)
    service.uploaded_docs_dir = tmp_path
    service.pipeline = None
    service.writer = None
    service.document_writer = None

    monkeypatch.setattr(service, "_calculate_file_hash", lambda _: "hash-1")
    monkeypatch.setattr(service, "_check_duplicate", lambda _: "doc-existing")

    src = tmp_path / "upload.pdf"
    src.write_bytes(b"%PDF-1.4")

    result = service.ingest_pdf(str(src), "upload.pdf")

    assert isinstance(result, IngestionResult)
    assert result.status == "duplicate"
    assert result.is_duplicate is True
    assert result.document_id == "doc-existing"


def test_save_file_sanitizes_name_and_appends_hash_on_collision(tmp_path):
    service = object.__new__(SemanticIngestionService)
    service.uploaded_docs_dir = tmp_path

    source = tmp_path / "src.pdf"
    source.write_bytes(b"pdf")

    first_name = service._save_file(source, "my bad:file?.pdf", "abcdef123456")
    assert first_name == "mybadfile.pdf"
    assert (tmp_path / first_name).exists()

    second_name = service._save_file(source, "my bad:file?.pdf", "abcdef123456")
    assert second_name == "mybadfile_abcdef12.pdf"
    assert (tmp_path / second_name).exists()
