"""LLM-based entity and relation extraction from text passages.

Sends a passage to the LLM with a strict JSON schema prompt,
parses the response, and validates it against Pydantic models.
"""

import json
import logging
import os

from openai import OpenAI

from backend.app.schemas.extraction import ExtractionResult
from backend.app.schemas.entities import VALID_ENTITY_TYPES
from backend.app.schemas.relations import VALID_RELATION_TYPES

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a knowledge graph extraction engine for academic papers.

Given a text passage, extract entities and relations.

## Entity types (use EXACTLY these)
- Concept: key technical terms, theories, abstractions
- Method: algorithms, models, techniques, architectures
- Dataset: named datasets used for training or evaluation
- Metric: quantitative measures (BLEU, accuracy, F1, etc.)
- Task: problem domains or application areas
- Author: person names
- Institution: universities, companies, labs

## Relation types (use EXACTLY these)
- MENTIONS: document discusses a concept
- INTRODUCES: document proposes a method
- USES: method uses a dataset or another method
- EVALUATED_ON: method is applied to a task
- MEASURED_BY: task is measured by a metric
- ABOUT: document addresses a task
- WROTE: author wrote the document
- AFFILIATED_WITH: author belongs to an institution

## Rules
1. Only extract entities explicitly mentioned in the text
2. Use the exact surface form from the text for "name"
3. Set "canonical_name" to a normalized version (title case, no abbreviation expansion)
4. confidence: 0.9-1.0 = explicit, 0.7-0.89 = strongly implied, 0.5-0.69 = inferred
5. Do NOT extract entities with confidence below 0.5
6. Return ONLY valid JSON, no markdown, no explanation

## Output format
{
  "entities": [
    {
      "type": "Method",
      "name": "Transformer",
      "canonical_name": "Transformer",
      "aliases": [],
      "confidence": 0.95
    }
  ],
  "relations": [
    {
      "type": "INTRODUCES",
      "source": "Transformer",
      "target": "Self-Attention",
      "confidence": 0.9
    }
  ]
}"""


class LLMExtractor:
    """Extracts entities and relations from text using an LLM."""

    def __init__(self, model: str = "gpt-4.1"):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model

    def extract(self, text: str, section_title: str | None = None) -> ExtractionResult:
        """Extract entities and relations from a passage.

        Args:
            text: The passage text to extract from.
            section_title: Optional section heading for context.

        Returns:
            ExtractionResult with validated entities and relations.

        Raises:
            ValueError: If extraction fails after retry.
        """
        if section_title:
            prompt = f"Section: {section_title}\n\nExtract entities and relations from this passage:\n\n{text}"
        else:
            prompt = f"Extract entities and relations from this passage:\n\n{text}"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content
        data = self._safe_parse(content)

        # Filter out invalid types before validation
        data = self._filter_invalid(data)

        return ExtractionResult(**data)

    def extract_batch(self, passages: list[dict]) -> list[ExtractionResult]:
        """Extract entities/relations for 2-3 passages in one LLM call."""
        if not passages:
            return []
        if len(passages) > 3:
            raise ValueError("extract_batch supports up to 3 passages per call")

        blocks: list[str] = []
        for item in passages:
            idx = item["index"]
            section = item.get("section_title") or "Unknown"
            text = item["text"]
            blocks.append(
                f"PASSAGE {idx}\nSection: {section}\nText:\n{text}"
            )
        prompt = (
            "Extract entities and relations for each passage below.\n"
            "Return JSON object with this exact shape:\n"
            '{"results":[{"index":<int>,"entities":[...],"relations":[...]}]}\n\n'
            + "\n\n".join(blocks)
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content
        parsed = self._safe_parse(content)
        raw_results = parsed.get("results", [])
        by_index = {
            int(item.get("index")): self._filter_invalid(
                {
                    "entities": item.get("entities", []),
                    "relations": item.get("relations", []),
                }
            )
            for item in raw_results
            if isinstance(item, dict) and "index" in item
        }

        extraction_results: list[ExtractionResult] = []
        for item in passages:
            cleaned = by_index.get(item["index"], {"entities": [], "relations": []})
            extraction_results.append(ExtractionResult(**cleaned))
        return extraction_results

    def _safe_parse(self, content: str) -> dict:
        """Parse JSON from LLM output with fallback for malformed responses."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: extract JSON object from surrounding text
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    pass
            logger.error("Failed to parse LLM output as JSON: %s", content[:200])
            raise ValueError("LLM returned unparseable output")

    def _filter_invalid(self, data: dict) -> dict:
        """Remove entities/relations with invalid types."""
        if "entities" in data:
            valid = []
            for e in data["entities"]:
                if e.get("type") in VALID_ENTITY_TYPES:
                    valid.append(e)
                else:
                    logger.warning("Dropping entity with unknown type: %s", e.get("type"))
            data["entities"] = valid

        if "relations" in data:
            valid = []
            for r in data["relations"]:
                if r.get("type") in VALID_RELATION_TYPES:
                    valid.append(r)
                else:
                    logger.warning("Dropping relation with unknown type: %s", r.get("type"))
            data["relations"] = valid

        return data
