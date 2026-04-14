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
from dataclasses import dataclass, field

from backend.app.services.extraction.llm_extractor import LLMExtractor
from backend.app.services.normalization.entity_normalizer import normalize_entities
from backend.app.services.normalization.relation_normalizer import normalize_relations
from backend.app.services.graph.graph_writer import GraphWriter
from backend.app.schemas.citation import InlineCitationRecord
from backend.app.schemas.passage import PassageRecord

logger = logging.getLogger(__name__)


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
    errors: list = field(default_factory=list)


class ExtractionPipeline:
    """Orchestrates extraction with normalization and provenance.

    This pipeline does NOT split text — it expects pre-built
    PassageRecords from the parsing layer.
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.extractor = LLMExtractor(model=model)
        self.writer = GraphWriter()

    def run(
        self,
        document_id: str,
        passages: list[PassageRecord],
        inline_citations: list[InlineCitationRecord] | None = None,
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

        # Count unique pages
        result.pages_total = len({p.page_number for p in passages})

        logger.info(
            "Pipeline started for %s: %d passages across %d pages",
            document_id,
            result.passages_total,
            result.pages_total,
        )

        for passage in passages:
            # Skip reference passages — they are stored structurally
            if getattr(passage, "content_type", "body") == "reference":
                result.reference_passages_skipped += 1
                logger.info(
                    "Skipping reference passage %d (page %d)",
                    passage.index,
                    passage.page_number,
                )
                continue

            try:
                # Step 1: Extract (with section context)
                extraction = self.extractor.extract(
                    passage.text, section_title=passage.section_title
                )

                raw_entity_count = len(extraction.entities)
                raw_relation_count = len(extraction.relations)

                # Step 2: Normalize entities
                extraction, name_map = normalize_entities(extraction)

                # Step 3: Normalize relations
                extraction = normalize_relations(extraction, name_map)

                result.entities_dropped += raw_entity_count - len(extraction.entities)
                result.relations_dropped += raw_relation_count - len(extraction.relations)

                # Step 4: Write to graph
                passage_citations = citations_by_passage.get(passage.passage_id, [])
                citation_labels = sorted(
                    {
                        label
                        for citation in passage_citations
                        for label in (citation.reference_labels or [])
                    }
                )
                write_result = self.writer.write(
                    extraction,
                    passage,
                    citation_metadata={
                        "citation_count": len(passage_citations),
                        "citation_labels": citation_labels,
                    },
                )

                result.passages_succeeded += 1
                result.entities_total += write_result["entities_written"]
                result.relations_total += write_result["relations_written"]
                result.evidence_total += write_result["evidence_written"]

                logger.info(
                    "Passage %d/%d (page %d): %d entities, %d relations, %d evidence",
                    passage.index + 1,
                    len(passages),
                    passage.page_number,
                    write_result["entities_written"],
                    write_result["relations_written"],
                    write_result["evidence_written"],
                )

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
