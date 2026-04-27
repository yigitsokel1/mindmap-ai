from backend.app.schemas.citation import InlineCitationRecord
from backend.app.schemas.passage import PassageRecord
from backend.app.services.extraction.pipeline import ExtractionPipeline, PipelineResult


def _make_passage(index: int, content_type: str = "body") -> PassageRecord:
    return PassageRecord(
        passage_id=f"pass-{index}",
        document_id="doc-1",
        index=index,
        text=f"text-{index}",
        page_number=1,
        section_title="Methods",
        content_type=content_type,
    )


def test_run_skips_reference_passages_and_uses_total_pages(monkeypatch):
    pipeline = object.__new__(ExtractionPipeline)
    pipeline.writer = type("Writer", (), {"write_batch": lambda self, batch: {"entities_written": 0, "relations_written": 0, "evidence_written": 0}})()
    pipeline.entity_linker = None
    pipeline.extractor = None

    captured = {}

    def fake_extract_passages_parallel(body_passages):
        captured["body_indices"] = [p.index for p in body_passages]
        return ([], {"total_llm_calls": 0, "avg_llm_ms": 0, "parallel_tasks_peak": 0})

    pipeline._extract_passages_parallel = fake_extract_passages_parallel

    result = pipeline.run(
        document_id="doc-1",
        passages=[_make_passage(0, "body"), _make_passage(1, "reference"), _make_passage(2, "body")],
        inline_citations=[],
        total_pages=12,
    )

    assert isinstance(result, PipelineResult)
    assert result.pages_total == 12
    assert result.passages_total == 3
    assert result.reference_passages_skipped == 1
    assert captured["body_indices"] == [0, 2]


def test_run_attaches_citation_summary_to_writer_batch(monkeypatch):
    pipeline = object.__new__(ExtractionPipeline)
    pipeline.entity_linker = None
    pipeline.extractor = None

    seen_batch = {}

    class Writer:
        def write_batch(self, batch):
            seen_batch["batch"] = batch
            return {"entities_written": 1, "relations_written": 1, "evidence_written": 1}

    pipeline.writer = Writer()

    extraction = type("Extraction", (), {"entities": [], "relations": []})()
    passage = _make_passage(0, "body")
    pipeline._extract_passages_parallel = lambda _: (
        [(passage, extraction, 0, 0, None, 10)],
        {"total_llm_calls": 1, "avg_llm_ms": 10, "parallel_tasks_peak": 1},
    )

    citation = InlineCitationRecord(
        citation_id="c1",
        document_id="doc-1",
        passage_id=passage.passage_id,
        page_number=1,
        raw_text="[12]",
        citation_style="numeric",
        start_char=1,
        end_char=4,
        reference_labels=["[12]", "[3]"],
    )

    result = pipeline.run(
        document_id="doc-1",
        passages=[passage],
        inline_citations=[citation],
        total_pages=1,
    )

    assert result.passages_succeeded == 1
    assert result.entities_total == 1
    assert result.relations_total == 1
    assert result.evidence_total == 1
    metadata = seen_batch["batch"][0][2]
    assert metadata["citation_count"] == 1
    assert metadata["citation_labels"] == ["[12]", "[3]"]
