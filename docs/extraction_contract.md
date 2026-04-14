# MindMap-AI: Extraction Contract

This document defines the exact input/output contract for the entity and relation extraction pipeline. All extraction logic — prompts, validators, parsers — must conform to these specifications.

**Version:** 1.0
**Status:** Active
**Depends on:** `ontology_v1.md`

---

## Overview

The extraction pipeline takes structured passages (produced by the parsing layer) and sends each one to an LLM to extract entities and relations conforming to the V1 ontology. The output is a validated JSON object per passage.

```
Passage (text + metadata)
    │
    ▼
LLM Extraction (system prompt + passage)
    │
    ▼
JSON Output (entities + relations)
    │
    ▼
Schema Validation (jsonschema)
    │
    ▼
Normalization (dedup, alias resolution)
    │
    ▼
Graph Storage (Neo4j)
```

---

## Input Specification

### Input Unit

The extraction unit is a single **passage** — a contiguous text span of approximately 500–2000 characters, segmented from the PDF after section detection.

Each passage is processed independently. Cross-passage entity resolution happens in the normalization layer, not during extraction.

### Input Payload

The following JSON payload is constructed by the orchestrator and sent to the LLM (embedded within the prompt):

```json
{
  "document_uid": "doc-001",
  "document_title": "Attention Is All You Need",
  "section_uid": "sec-003",
  "section_title": "3. Model Architecture",
  "passage_uid": "pass-042",
  "passage_text": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
  "page": 2,
  "extraction_types": ["entities", "relations"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_uid` | string | Yes | UUID of the parent document |
| `document_title` | string | Yes | Title for context (helps LLM understand domain) |
| `section_uid` | string | Yes | UUID of the parent section |
| `section_title` | string | Yes | Section heading for context |
| `passage_uid` | string | Yes | UUID of this passage |
| `passage_text` | string | Yes | The raw text to extract from |
| `page` | integer | Yes | PDF page number (0-indexed) |
| `extraction_types` | list[string] | Yes | What to extract: `["entities"]`, `["relations"]`, or `["entities", "relations"]` |

Additional structural context supplied by parsing layer (not mandatory for LLM prompt body in V1):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `citations_present` | boolean | No | Whether passage contains at least one inline citation mention |
| `citation_labels` | list[string] | No | Compact normalized labels (e.g., `["vaswani:2017"]`) |

### Extraction Modes

- **Metadata pass** (`extraction_types: ["entities"]`): Used on title pages and author blocks to extract Author, Institution entities without relation extraction.
- **Full pass** (`extraction_types: ["entities", "relations"]`): Used on body passages to extract all entity types and their relations.

---

## Output Specification

### Output JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["document_uid", "passage_uid", "entities", "relations"],
  "properties": {
    "document_uid": {
      "type": "string",
      "description": "Echo of input document_uid for traceability"
    },
    "passage_uid": {
      "type": "string",
      "description": "Echo of input passage_uid for traceability"
    },
    "entities": {
      "type": "array",
      "items": { "$ref": "#/definitions/ExtractedEntity" }
    },
    "relations": {
      "type": "array",
      "items": { "$ref": "#/definitions/ExtractedRelation" }
    }
  },
  "definitions": {
    "ExtractedEntity": {
      "type": "object",
      "required": ["temp_id", "type", "name", "surface_text", "confidence"],
      "properties": {
        "temp_id": {
          "type": "string",
          "description": "Temporary ID scoped to this extraction batch (e.g., 'e1', 'e2'). Used as reference in relations."
        },
        "type": {
          "type": "string",
          "enum": ["Author", "Institution", "Concept", "Method", "Dataset", "Metric", "Task"],
          "description": "Entity type from V1 ontology"
        },
        "name": {
          "type": "string",
          "description": "Best-guess canonical name for this entity"
        },
        "surface_text": {
          "type": "string",
          "description": "Exact text span from the passage where this entity appears. Must be a substring of passage_text."
        },
        "confidence": {
          "type": "number",
          "minimum": 0.5,
          "maximum": 1.0,
          "description": "Extraction confidence per the confidence rubric"
        },
        "attributes": {
          "type": "object",
          "description": "Optional type-specific attributes",
          "properties": {
            "definition": {
              "type": "string",
              "description": "For Concept: extracted definition"
            },
            "description": {
              "type": "string",
              "description": "For Method: brief description"
            },
            "domain": {
              "type": "string",
              "description": "For Dataset: domain area"
            },
            "institution_type": {
              "type": "string",
              "enum": ["university", "company", "lab", "government"],
              "description": "For Institution: organization type"
            }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    },
    "ExtractedRelation": {
      "type": "object",
      "required": ["type", "source", "target", "surface_text", "confidence"],
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "WROTE",
            "AFFILIATED_WITH",
            "MENTIONS",
            "INTRODUCES",
            "USES",
            "EVALUATED_ON",
            "MEASURED_BY",
            "ABOUT"
          ],
          "description": "Relation type from V1 ontology"
        },
        "source": {
          "type": "string",
          "description": "temp_id of the source entity, or '__DOCUMENT__' for document-level relations (MENTIONS, INTRODUCES, ABOUT)"
        },
        "target": {
          "type": "string",
          "description": "temp_id of the target entity"
        },
        "surface_text": {
          "type": "string",
          "description": "Exact supporting text span from the passage"
        },
        "confidence": {
          "type": "number",
          "minimum": 0.5,
          "maximum": 1.0,
          "description": "Extraction confidence per the confidence rubric"
        }
      },
      "additionalProperties": false
    }
  }
}
```

### The `__DOCUMENT__` Source

For document-level relations (`MENTIONS`, `INTRODUCES`, `ABOUT`), the source is the document itself, not an extracted entity. In these cases, `source` should be set to the string literal `"__DOCUMENT__"`.

Example:
```json
{
  "type": "INTRODUCES",
  "source": "__DOCUMENT__",
  "target": "e3",
  "surface_text": "We propose a new simple network architecture, the Transformer",
  "confidence": 0.95
}
```

The graph writer resolves `__DOCUMENT__` to the actual Document node using `document_uid`.

---

## Confidence Rubric

The LLM receives this rubric in the system prompt and self-assesses confidence:

| Score | Meaning | Guidance |
|-------|---------|----------|
| **0.90 – 1.00** | Explicit | Entity/relation is directly and unambiguously stated in the text |
| **0.70 – 0.89** | Strong implication | Entity/relation is strongly implied, uses near-synonyms, or is clear from immediate context |
| **0.50 – 0.69** | Inference | Entity/relation requires interpretation or reading between the lines |
| **Below 0.50** | Do not emit | The extraction is too uncertain to be useful |

### Downstream Filtering

After extraction, a configurable **confidence threshold** (default: `0.6`) filters out low-confidence extractions before normalization and storage. Extractions below this threshold are logged but not persisted to the graph.

This threshold is separate from the LLM's 0.5 floor — it provides an additional quality gate that can be tuned per deployment.

---

## Provenance Model

Every extracted entity and relation carries provenance through the `surface_text` field and the passage metadata.

### At Extraction Time

Each extraction output includes:
- `passage_uid` — which passage was processed
- `document_uid` — which document it belongs to
- `surface_text` on every entity and relation — the exact span that justifies the extraction

### At Storage Time

The graph writer creates Evidence nodes:

```
For each entity:
  Evidence {
    uid: generated,
    passage_uid: from extraction output,
    document_uid: from extraction output,
    confidence: from entity.confidence,
    extraction_method: "llm_{model_name}",
    extracted_at: now(),
    surface_text: from entity.surface_text
  }
  (Evidence)-[:FROM_PASSAGE]->(Passage)
  (Evidence)-[:IDENTIFIES]->(Entity)

For each relation:
  Evidence {
    uid: generated,
    passage_uid: from extraction output,
    document_uid: from extraction output,
    confidence: from relation.confidence,
    extraction_method: "llm_{model_name}",
    extracted_at: now(),
    surface_text: from relation.surface_text,
    citation_count: number of inline citations in the source passage,
    citation_labels: normalized labels from parsing stage
  }
  (Evidence)-[:FROM_PASSAGE]->(Passage)
  Semantic edge gets evidence_uid appended to evidence_uids list
```

---

## Error Handling

### 1. JSON Parse Failure

The LLM sometimes produces malformed JSON (unclosed brackets, trailing commas, etc.).

**Strategy:**
1. Attempt `json.loads()` on the raw output
2. If it fails, send a follow-up prompt: "The previous output was not valid JSON. Please fix it and return only the corrected JSON."
3. If the retry also fails, log the raw output and mark the passage as `extraction_status: "failed"`
4. Do not retry more than once — repeated failures indicate a prompt or model issue

### 2. Schema Validation Failure

The JSON parses but doesn't conform to the schema.

**Strategy:**
1. Validate with `jsonschema.validate()` against the output schema
2. If validation fails, attempt **partial salvage**:
   - Keep entities that individually validate
   - Keep relations whose referenced `temp_id`s exist in the valid entity set
   - Discard the rest
3. Log all discarded items with the validation error
4. If zero valid items remain, mark passage as `extraction_status: "failed"`

### 3. Unknown Entity Type

An entity has a `type` not in the allowed enum.

**Strategy:** Reject the entity. Log it as `unknown_entity_type`. Do not attempt to guess the correct type.

### 4. Unknown Relation Type

A relation has a `type` not in the allowed enum.

**Strategy:** Reject the relation. Log it as `unknown_relation_type`.

### 5. Dangling References

A relation's `source` or `target` references a `temp_id` not present in the entities list (and is not `__DOCUMENT__`).

**Strategy:** Reject that relation. Log it as `dangling_reference`. Keep the entities — they may still be valid.

### 6. Empty Extraction

The LLM returns `{"entities": [], "relations": []}`.

**Strategy:** This is valid. Some passages contain no extractable entities (e.g., acknowledgments, references section, mathematical notation). Mark the passage as `extraction_status: "empty"`.

### 7. Duplicate Entities Within a Batch

The LLM extracts the same entity twice with different `temp_id`s.

**Strategy:** The extraction layer does not deduplicate — this is the normalization layer's responsibility. Both entities are passed through. The normalization layer will merge them by `canonical_name` matching.

---

## Extraction Strategy

### V1: Single-Passage Extraction

Each passage is sent as one independent LLM call.

**Rationale:**
- **Provenance precision**: Every entity/relation maps to exactly one passage
- **Error isolation**: One passage failure doesn't affect others
- **Parallelizable**: Passages can be processed concurrently with async workers
- **Simpler debugging**: Each extraction is self-contained

**Trade-offs:**
- Higher token cost (more LLM calls)
- No cross-passage context (entity coreference handled by normalization layer)
- Repeated entity extraction for entities mentioned across multiple passages

### V2: Batch Extraction (Future)

Multiple passages from the same section sent in one call. Benefits:
- Lower token cost
- Cross-passage entity coreference within a section
- Better context for ambiguous extractions

Batch extraction will require changes to the output schema (array of passage results) and provenance model (multi-passage evidence). This is a V2 concern.

---

## Pipeline Processing Order

For a single document:

```
1. Parse PDF → pages with text
2. Detect sections → Section nodes with titles and levels
3. Segment passages → Passage nodes (500-2000 chars each)
4. Store structure → Document, Section, Passage, ReferenceEntry, InlineCitation nodes + structural edges in Neo4j
5. For each passage:
   a. Build extraction input payload
   b. Send to LLM
   c. Parse JSON response
   d. Validate against schema
   e. Apply confidence threshold filter
   f. Pass valid extractions to normalization
6. Normalization → deduplicate entities, resolve aliases
7. Graph storage → MERGE entities, CREATE evidence, create semantic edges
8. Mark passage as extraction_status: "completed"
```

### Concurrency

- Passages within a document can be extracted concurrently (async)
- Multiple documents can be processed concurrently
- Graph writes should be serialized per document to avoid race conditions on MERGE operations

---

## Example: Full Extraction Cycle

### Input

```json
{
  "document_uid": "doc-001",
  "document_title": "Attention Is All You Need",
  "section_uid": "sec-005",
  "section_title": "5. Training",
  "passage_uid": "pass-089",
  "passage_text": "We trained on the standard WMT 2014 English-German dataset consisting of about 4.5 million sentence pairs. We used beam search with a beam size of 4 and length penalty alpha = 0.6. The resulting model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task.",
  "page": 7,
  "extraction_types": ["entities", "relations"]
}
```

### Expected Output

```json
{
  "document_uid": "doc-001",
  "passage_uid": "pass-089",
  "entities": [
    {
      "temp_id": "e1",
      "type": "Dataset",
      "name": "WMT 2014 English-German",
      "surface_text": "WMT 2014 English-German dataset",
      "confidence": 0.95,
      "attributes": {
        "domain": "machine translation"
      }
    },
    {
      "temp_id": "e2",
      "type": "Task",
      "name": "English-to-German Translation",
      "surface_text": "English-to-German translation task",
      "confidence": 0.92
    },
    {
      "temp_id": "e3",
      "type": "Metric",
      "name": "BLEU",
      "surface_text": "28.4 BLEU",
      "confidence": 0.98
    },
    {
      "temp_id": "e4",
      "type": "Method",
      "name": "Beam Search",
      "surface_text": "beam search with a beam size of 4",
      "confidence": 0.85,
      "attributes": {
        "description": "Search algorithm with beam size 4 and length penalty 0.6"
      }
    }
  ],
  "relations": [
    {
      "type": "EVALUATED_ON",
      "source": "e4",
      "target": "e2",
      "surface_text": "model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task",
      "confidence": 0.88
    },
    {
      "type": "USES",
      "source": "e4",
      "target": "e1",
      "surface_text": "trained on the standard WMT 2014 English-German dataset",
      "confidence": 0.90
    },
    {
      "type": "MEASURED_BY",
      "source": "e2",
      "target": "e3",
      "surface_text": "achieves 28.4 BLEU on the WMT 2014 English-to-German translation task",
      "confidence": 0.93
    },
    {
      "type": "ABOUT",
      "source": "__DOCUMENT__",
      "target": "e2",
      "surface_text": "English-to-German translation task",
      "confidence": 0.80
    }
  ]
}
```

---

## Relation Type Validation Rules

Not all source-target type combinations are valid. The extraction validator enforces:

| Relation | Valid Source Types | Valid Target Types |
|----------|-------------------|-------------------|
| `WROTE` | Author | (resolved to Document via `__DOCUMENT__`) |
| `AFFILIATED_WITH` | Author | Institution |
| `MENTIONS` | `__DOCUMENT__` | Concept |
| `INTRODUCES` | `__DOCUMENT__` | Method |
| `USES` | Method | Dataset, Method |
| `EVALUATED_ON` | Method | Task |
| `MEASURED_BY` | Task | Metric |
| `ABOUT` | `__DOCUMENT__` | Task |

Relations with invalid source/target type combinations are rejected with a `type_mismatch` log entry.
