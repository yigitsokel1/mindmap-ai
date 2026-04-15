"""Semantic ingestion service.

The primary ingestion path for MindMap-AI. Replaces the legacy
chunk/embedding ingestion with a semantic KG extraction pipeline.

Flow:
  PDF upload → duplicate check → file save → PDF parse
    → page-aware passage splitting → extraction pipeline → graph write
"""

import hashlib
import inspect
import logging
import shutil
import uuid
import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable

from backend.app.core.db import Neo4jDatabase
from backend.app.services.parsing.document_parser import parse_document, ParseResult
from backend.app.services.extraction.pipeline import ExtractionPipeline, PipelineResult
from backend.app.services.graph.graph_writer import GraphWriter

logger = logging.getLogger("uvicorn.error")


@dataclass
class IngestionResult:
    """Result of a semantic ingestion run."""

    document_id: str
    file_name: str
    saved_file_name: str
    is_duplicate: bool
    status: str  # "success", "duplicate", "error"
    pages_total: int = 0
    passages_total: int = 0
    passages_succeeded: int = 0
    passages_failed: int = 0
    entities_written: int = 0
    relations_written: int = 0
    evidence_written: int = 0
    entities_dropped: int = 0
    relations_dropped: int = 0
    sections_total: int = 0
    references_total: int = 0
    reference_entries_total: int = 0
    inline_citations_total: int = 0
    citation_links_total: int = 0
    body_passages_total: int = 0
    reference_passages_skipped: int = 0
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict:
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
            "errors": self.errors,
        }


class SemanticIngestionService:
    """Primary ingestion service using semantic KG extraction."""

    def __init__(self, model: str = "gpt-4.1"):
        self.db = Neo4jDatabase()
        self.pipeline = ExtractionPipeline(model=model)
        self.writer = GraphWriter()
        self.uploaded_docs_dir = Path(__file__).parent.parent.parent.parent / "uploaded_docs"
        self.uploaded_docs_dir.mkdir(exist_ok=True)

    def ingest_pdf(
        self,
        file_path: str,
        file_name: str,
        progress_callback: Callable[[str, dict | None], None] | None = None,
    ) -> IngestionResult:
        """Ingest a PDF through the semantic extraction pipeline.

        Args:
            file_path: Path to the PDF file (temp upload location).
            file_name: Original filename.

        Returns:
            IngestionResult with full extraction diagnostics.
        """
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        started_at = perf_counter()
        self._notify(progress_callback, "uploaded", {"file_name": file_name})

        # Step 1: Duplicate check
        file_hash = self._calculate_file_hash(pdf_path)
        existing_id = self._check_duplicate(file_hash)
        if existing_id:
            logger.info("Duplicate detected: %s (existing: %s)", file_name, existing_id)
            return IngestionResult(
                document_id=existing_id,
                file_name=file_name,
                saved_file_name="",
                is_duplicate=True,
                status="duplicate",
            )

        # Step 2: Save file
        saved_name = self._save_file(pdf_path, file_name, file_hash)

        # Step 3: Generate document ID
        document_id = str(uuid.uuid4())

        # Step 4: Parse PDF into section-aware passages
        self._notify(progress_callback, "parsing")
        saved_path = self.uploaded_docs_dir / saved_name
        parse_result = parse_document(
            str(saved_path),
            document_id,
            progress_callback=progress_callback,
        )
        logger.info(
            "Parsed document metrics: document_id=%s pages_total=%d sections_total=%d body_passages_total=%d",
            document_id,
            len(parse_result.pages),
            len(parse_result.sections),
            len(parse_result.passages),
        )

        # Step 5: Ensure document node has full metadata
        self._store_document_metadata(document_id, file_name, file_hash, saved_name)

        # Step 6: Write section nodes to graph
        if parse_result.sections:
            self._notify(progress_callback, "writing_graph", {"subphase": "sections"})
            self.writer.write_sections(parse_result.sections, document_id)

        # Step 7: Write reference entries to graph
        if parse_result.references:
            self._notify(progress_callback, "writing_graph", {"subphase": "references"})
            self.writer.write_references(parse_result.references, document_id)

        # Step 8: Run extraction pipeline (on body passages only)
        self._notify(progress_callback, "extracting_semantics")
        pipeline_result = self.pipeline.run(
            document_id=document_id,
            passages=parse_result.passages,
            inline_citations=parse_result.inline_citations,
            total_pages=len(parse_result.pages),
        )

        # Step 9: Write inline citation nodes and links
        # This must run after passage writes from the extraction pipeline so
        # (Passage)-[:HAS_INLINE_CITATION]->(InlineCitation) links can resolve.
        inline_citation_stats = {"citations_written": 0, "citation_links_written": 0}
        if parse_result.inline_citations:
            self._notify(progress_callback, "writing_graph", {"subphase": "inline_citations"})
            inline_citation_stats = self.writer.write_inline_citations(
                parse_result.inline_citations,
                parse_result.citation_links,
            )
        self._notify(progress_callback, "completed", {"document_id": document_id})
        elapsed = perf_counter() - started_at

        logger.info(
            "Semantic ingestion complete for %s: %d entities, %d relations, "
            "%d evidence, %d sections, %d references, %d inline citations, %d citation links",
            file_name,
            pipeline_result.entities_total,
            pipeline_result.relations_total,
            pipeline_result.evidence_total,
            len(parse_result.sections),
            len(parse_result.references),
            len(parse_result.inline_citations),
            len(parse_result.citation_links),
        )
        logger.info(
            "Dropped summary for %s: entities_dropped=%d relations_dropped=%d "
            "inline_citations_written=%d citation_links_written=%d elapsed=%.2fs",
            file_name,
            pipeline_result.entities_dropped,
            pipeline_result.relations_dropped,
            inline_citation_stats["citations_written"],
            inline_citation_stats["citation_links_written"],
            elapsed,
        )
        logger.info(
            "Semantic ingestion total duration: file=%s document_id=%s total_duration_ms=%d",
            file_name,
            document_id,
            int(elapsed * 1000),
        )
        logger.info(
            "Ingestion summary telemetry: document_id=%s passage_count=%d parallel_tasks_peak=%d total_llm_calls=%d avg_llm_ms=%d total_ingest_ms=%d",
            document_id,
            pipeline_result.passages_succeeded + pipeline_result.passages_failed,
            pipeline_result.parallel_tasks_peak,
            pipeline_result.total_llm_calls,
            pipeline_result.avg_llm_ms,
            int(elapsed * 1000),
        )
        logger.info(
            "Ingestion passage metrics: document_id=%s pages_total=%d sections_total=%d body_passages_total=%d reference_passages_skipped=%d",
            document_id,
            len(parse_result.pages),
            len(parse_result.sections),
            len(parse_result.passages),
            pipeline_result.reference_passages_skipped,
        )

        return IngestionResult(
            document_id=document_id,
            file_name=file_name,
            saved_file_name=saved_name,
            is_duplicate=False,
            status="success",
            pages_total=len(parse_result.pages),
            passages_total=pipeline_result.passages_total,
            passages_succeeded=pipeline_result.passages_succeeded,
            passages_failed=pipeline_result.passages_failed,
            entities_written=pipeline_result.entities_total,
            relations_written=pipeline_result.relations_total,
            evidence_written=pipeline_result.evidence_total,
            entities_dropped=pipeline_result.entities_dropped,
            relations_dropped=pipeline_result.relations_dropped,
            sections_total=len(parse_result.sections),
            references_total=len(parse_result.references),
            reference_entries_total=len(parse_result.references),
            inline_citations_total=len(parse_result.inline_citations),
            citation_links_total=len(parse_result.citation_links),
            body_passages_total=len(parse_result.passages),
            reference_passages_skipped=pipeline_result.reference_passages_skipped,
            errors=pipeline_result.errors,
        )

    @staticmethod
    def _notify(
        progress_callback: Callable[[str, dict | None], None] | None,
        stage: str,
        details: dict | None = None,
    ) -> None:
        if not progress_callback:
            return
        maybe_awaitable = progress_callback(stage, details)
        if inspect.isawaitable(maybe_awaitable):
            try:
                asyncio.get_running_loop()
                has_running_loop = True
            except RuntimeError:
                has_running_loop = False
            if has_running_loop:
                asyncio.create_task(maybe_awaitable)
                return
            asyncio.run(maybe_awaitable)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _check_duplicate(self, file_hash: str) -> str | None:
        """Check Neo4j for existing document with same file_hash."""
        try:
            if not self.db.driver:
                self.db.connect()

            result, _, _ = self.db.execute_query_with_retry(
                "MATCH (d:Document) WHERE d['file_hash'] = $hash RETURN d.uid AS uid LIMIT 1",
                {"hash": file_hash},
            )
            if result:
                return result[0]["uid"]
            return None
        except Exception as e:
            logger.warning("Duplicate check failed: %s", e)
            return None

    def _save_file(self, source: Path, file_name: str, file_hash: str) -> str:
        """Save uploaded file to uploaded_docs/. Returns saved filename."""
        safe_name = "".join(c for c in file_name if c.isalnum() or c in "._-")
        if not safe_name:
            safe_name = "uploaded_file.pdf"

        target = self.uploaded_docs_dir / safe_name
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            safe_name = f"{stem}_{file_hash[:8]}{suffix}"
            target = self.uploaded_docs_dir / safe_name

        shutil.copy2(source, target)
        logger.info("Saved file to %s", target)
        return safe_name

    def _store_document_metadata(
        self, document_id: str, file_name: str, file_hash: str, saved_name: str
    ):
        """Update Document node with file metadata."""
        try:
            if not self.db.driver:
                self.db.connect()

            self.db.execute_query_with_retry(
                "MERGE (d:Document {uid: $uid}) "
                "SET d.file_name = $file_name, "
                "    d.file_hash = $file_hash, "
                "    d.saved_file_name = $saved_name",
                {
                    "uid": document_id,
                    "file_name": file_name,
                    "file_hash": file_hash,
                    "saved_name": saved_name,
                },
            )
        except Exception as e:
            logger.error("Failed to store document metadata: %s", e)
