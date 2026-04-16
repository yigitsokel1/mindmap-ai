"""Extraction pipeline orchestrator.

V3 (Sprint 4): Accepts pre-built PassageRecords from the parsing layer.
Splitting is no longer this module's responsibility.

Flow:
  PassageRecords (from parsing layer)
    → LLMExtractor
    → EntityNormalizer
    → RelationNormalizer
    → GraphWriter (with provenance)
"""

import logging
import asyncio
import os
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from backend.app.services.extraction.llm_extractor import LLMExtractor
from backend.app.services.normalization.entity_normalizer import normalize_entities
from backend.app.services.normalization.entity_linker import EntityLinker
from backend.app.services.normalization.relation_normalizer import normalize_relations
from backend.app.services.graph.graph_writer import GraphWriter
from backend.app.schemas.citation import InlineCitationRecord
from backend.app.schemas.passage import PassageRecord

logger = logging.getLogger("uvicorn.error")


@dataclass
class PipelineResult:
    """Summary of a pipeline run."""

    document_id: str
    pages_total: int = 0
    passages_total: int = 0
    passages_succeeded: int = 0
    passages_failed: int = 0
    entities_total: int = 0
    relations_total: int = 0
    evidence_total: int = 0
    entities_dropped: int = 0
    relations_dropped: int = 0
    reference_passages_skipped: int = 0
    total_llm_calls: int = 0
    avg_llm_ms: int = 0
    parallel_tasks_peak: int = 0
    errors: list = field(default_factory=list)


class ExtractionPipeline:
    """Orchestrates extraction with normalization and provenance.

    This pipeline does NOT split text — it expects pre-built
    PassageRecords from the parsing layer.
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.extractor = LLMExtractor(model=model)
        self.entity_linker = EntityLinker()
        self.writer = GraphWriter()

    def run(
        self,
        document_id: str,
        passages: list[PassageRecord],
        inline_citations: list[InlineCitationRecord] | None = None,
        total_pages: int | None = None,
    ) -> PipelineResult:
        """Run extraction on pre-built passages.

        Args:
            document_id: UID of the source document.
            passages: List of PassageRecords from the parsing layer.

        Returns:
            PipelineResult with extraction statistics.
        """
        result = PipelineResult(document_id=document_id)
        result.passages_total = len(passages)
        citations_by_passage: dict[str, list[InlineCitationRecord]] = {}
        for citation in inline_citations or []:
            citations_by_passage.setdefault(citation.passage_id, []).append(citation)

        # Use parser-authoritative page count when available.
        result.pages_total = int(total_pages) if total_pages is not None else len({p.page_number for p in passages})

        body_passages = [
            passage for passage in passages if getattr(passage, "content_type", "body") != "reference"
        ]
        result.reference_passages_skipped = len(passages) - len(body_passages)
        extraction_input_count = len(body_passages)
        logger.info(
            "Pipeline passage counts: document_id=%s total_passages=%d extraction_input_passages=%d skipped_reference=%d skipped_total=%d pages_total=%d",
            document_id,
            result.passages_total,
            extraction_input_count,
            result.reference_passages_skipped,
            result.reference_passages_skipped,
            result.pages_total,
        )

        extracted_records, telemetry = self._extract_passages_parallel(body_passages)
        result.total_llm_calls = telemetry["total_llm_calls"]
        result.avg_llm_ms = telemetry["avg_llm_ms"]
        result.parallel_tasks_peak = telemetry["parallel_tasks_peak"]

        write_batch_items: list[tuple[Any, PassageRecord, dict | None]] = []
        extraction_durations_ms: list[int] = []
        for passage, extraction, raw_entity_count, raw_relation_count, error, duration_ms in extracted_records:
            # Skip reference passages — they are stored structurally
            if error is not None:
                result.passages_failed += 1
                result.errors.append(
                    {
                        "passage_index": passage.index,
                        "page_number": passage.page_number,
                        "error": str(error),
                    }
                )
                logger.error(
                    "Passage %d/%d (page %d) failed: %s",
                    passage.index + 1,
                    len(passages),
                    passage.page_number,
                    error,
                )
                continue
            extraction_durations_ms.append(duration_ms)

            try:
                result.entities_dropped += raw_entity_count - len(extraction.entities)
                result.relations_dropped += raw_relation_count - len(extraction.relations)

                passage_citations = citations_by_passage.get(passage.passage_id, [])
                citation_labels = sorted(
                    {
                        label
                        for citation in passage_citations
                        for label in (citation.reference_labels or [])
                    }
                )
                write_batch_items.append(
                    (
                        extraction,
                        passage,
                        {
                        "citation_count": len(passage_citations),
                        "citation_labels": citation_labels,
                        },
                    )
                )
                result.passages_succeeded += 1

            except Exception as e:
                result.passages_failed += 1
                result.errors.append(
                    {
                        "passage_index": passage.index,
                        "page_number": passage.page_number,
                        "error": str(e),
                    }
                )
                logger.error(
                    "Passage %d/%d (page %d) failed: %s",
                    passage.index + 1,
                    len(passages),
                    passage.page_number,
                    e,
                )

        for i in range(0, len(write_batch_items), 25):
            batch = write_batch_items[i : i + 25]
            write_result = self.writer.write_batch(batch)
            result.entities_total += write_result["entities_written"]
            result.relations_total += write_result["relations_written"]
            result.evidence_total += write_result["evidence_written"]

        if extraction_durations_ms:
            logger.info(
                "Extraction duration distribution: document_id=%s count=%d min_ms=%d avg_ms=%d max_ms=%d",
                document_id,
                len(extraction_durations_ms),
                min(extraction_durations_ms),
                int(sum(extraction_durations_ms) / len(extraction_durations_ms)),
                max(extraction_durations_ms),
            )
        else:
            logger.info(
                "Extraction duration distribution: document_id=%s count=0 min_ms=0 avg_ms=0 max_ms=0",
                document_id,
            )

        logger.info(
            "Extraction summary telemetry: document_id=%s passage_count=%d parallel_tasks_peak=%d total_llm_calls=%d avg_llm_ms=%d",
            document_id,
            extraction_input_count,
            result.parallel_tasks_peak,
            result.total_llm_calls,
            result.avg_llm_ms,
        )

        logger.info(
            "Pipeline completed for %s: %d/%d passages (%d ref skipped), "
            "%d entities (%d dropped), %d relations (%d dropped), %d evidence",
            document_id,
            result.passages_succeeded,
            result.passages_total,
            result.reference_passages_skipped,
            result.entities_total,
            result.entities_dropped,
            result.relations_total,
            result.relations_dropped,
            result.evidence_total,
        )

        return result

    def _extract_passages_parallel(
        self,
        passages: list[PassageRecord],
    ) -> tuple[
        list[tuple[PassageRecord, object, int, int, Exception | None, int]],
        dict[str, int],
    ]:
        """Extract and normalize passages in parallel for throughput gains."""

        concurrency_limit = int(os.getenv("EXTRACTION_CONCURRENCY_LIMIT", "5"))
        batch_size = int(os.getenv("EXTRACTION_BATCH_SIZE", "1"))
        batch_size = 2 if batch_size == 2 else 1
        semaphore = asyncio.Semaphore(concurrency_limit)

        llm_call_durations_ms: list[int] = []
        active_tasks = 0
        parallel_tasks_peak = 0

        async def _extract_batch(
            batch_passages: list[PassageRecord],
        ) -> list[tuple[PassageRecord, object, int, int, Exception | None, int]]:
            nonlocal active_tasks, parallel_tasks_peak
            async with semaphore:
                active_tasks += 1
                if active_tasks > parallel_tasks_peak:
                    parallel_tasks_peak = active_tasks
                batch_started_at = perf_counter()
                for passage in batch_passages:
                    logger.info(
                        "Extraction started: passage_index=%d page=%d chars=%d",
                        passage.index,
                        passage.page_number,
                        len(passage.text or ""),
                    )
                try:
                    llm_started_at = perf_counter()
                    extractions = await asyncio.to_thread(
                        self.extractor.extract_batch,
                        [
                            {
                                "index": passage.index,
                                "section_title": passage.section_title,
                                "text": passage.text,
                            }
                            for passage in batch_passages
                        ],
                    )
                    llm_duration_ms = int((perf_counter() - llm_started_at) * 1000)
                    llm_call_durations_ms.append(llm_duration_ms)
                    results: list[tuple[PassageRecord, object, int, int, Exception | None, int]] = []
                    for passage, extraction in zip(batch_passages, extractions, strict=False):
                        raw_entity_count = len(extraction.entities)
                        raw_relation_count = len(extraction.relations)
                        normalization_started_at = perf_counter()
                        extraction, name_map = normalize_entities(extraction)
                        extraction, name_map = self.entity_linker.link_extraction(extraction, name_map)
                        extraction = normalize_relations(extraction, name_map)
                        normalization_duration_ms = int((perf_counter() - normalization_started_at) * 1000)
                        total_duration_ms = int((perf_counter() - batch_started_at) * 1000)
                        logger.info(
                            "Extraction completed: passage_index=%d duration_ms=%d llm_duration_ms=%d normalization_duration_ms=%d entities=%d relations=%d",
                            passage.index,
                            total_duration_ms,
                            llm_duration_ms,
                            normalization_duration_ms,
                            len(extraction.entities),
                            len(extraction.relations),
                        )
                        results.append(
                            (
                                passage,
                                extraction,
                                raw_entity_count,
                                raw_relation_count,
                                None,
                                total_duration_ms,
                            )
                        )
                    return results
                except Exception as exc:
                    failure_duration_ms = int((perf_counter() - batch_started_at) * 1000)
                    failed: list[tuple[PassageRecord, object, int, int, Exception | None, int]] = []
                    for passage in batch_passages:
                        logger.error(
                            "Extraction failed: passage_index=%d duration_ms=%d error=%s",
                            passage.index,
                            failure_duration_ms,
                            exc,
                        )
                        failed.append((passage, None, 0, 0, exc, failure_duration_ms))
                    return failed
                finally:
                    active_tasks -= 1

        async def _run() -> list[tuple[PassageRecord, object, int, int, Exception | None, int]]:
            grouped_passages = [passages[i : i + batch_size] for i in range(0, len(passages), batch_size)]
            tasks = [_extract_batch(batch) for batch in grouped_passages]
            logger.info(
                "Extraction concurrency: mode=async_parallel concurrency_limit=%d batch_size=%d total_tasks=%d max_parallel_tasks=%d",
                concurrency_limit,
                batch_size,
                len(tasks),
                min(concurrency_limit, len(tasks)),
            )
            if not tasks:
                return []
            grouped = await asyncio.gather(*tasks, return_exceptions=True)
            flattened: list[tuple[PassageRecord, object, int, int, Exception | None, int]] = []
            for bucket in grouped:
                if isinstance(bucket, Exception):
                    logger.error("Extraction task group failed: %s", bucket)
                    continue
                flattened.extend(bucket)
            return flattened

        records = asyncio.run(_run())
        avg_llm_ms = int(sum(llm_call_durations_ms) / len(llm_call_durations_ms)) if llm_call_durations_ms else 0
        telemetry = {
            "total_llm_calls": len(llm_call_durations_ms),
            "avg_llm_ms": avg_llm_ms,
            "parallel_tasks_peak": parallel_tasks_peak,
        }
        return records, telemetry
