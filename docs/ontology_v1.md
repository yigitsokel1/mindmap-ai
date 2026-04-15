# MindMap-AI: V1 Ontology

This document defines the canonical schema for the Semantic Knowledge Graph. All extraction, normalization, and storage logic must conform to these definitions.

Source of truth for traversal contracts: `docs/graph_contract.md`.

**Version:** 1.0
**Status:** Active
**Scope:** Academic / technical paper analysis

---

## Design Principles

1. **Extraction-feasible** — Every node and edge type must be reliably extractable by an LLM from a single passage or section header. Types that require cross-document resolution (e.g., Citation) are deferred to V2.

2. **Provenance-first** — Every semantic edge is linked to one or more Evidence nodes. No relation exists without a traceable source passage.

3. **Normalization-ready** — Semantic entities carry both `canonical_name` (the resolved, deduplicated name) and `surface_forms` (all observed textual variants). This separation enables the normalization layer to operate independently from extraction.

4. **Minimal viable coverage** — 11 node types and 13 edge types. Broad enough to capture the essential structure of academic papers; narrow enough to keep extraction quality manageable.

---

## Node Types

### Structural Nodes

These represent the physical structure of the ingested document.

#### Document

The root entity. Represents one uploaded PDF.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `title` | string | Yes | Full paper title |
| `file_hash` | string | Yes | MD5 hash of source file (deduplication) |
| `file_name` | string | Yes | Original uploaded filename |
| `saved_file_name` | string | No | Sanitized filename in `uploaded_docs/` |
| `abstract` | string | No | Paper abstract if extracted |
| `year` | integer | No | Publication year |
| `doi` | string | No | Digital Object Identifier |
| `created_at` | datetime | Yes | Ingestion timestamp |

#### Section

A structural division of the document (e.g., "3. Model Architecture").

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `title` | string | Yes | Section heading text |
| `ordinal` | integer | Yes | 0-indexed position within the document |
| `level` | integer | Yes | Heading depth (1 = top-level, 2 = subsection, etc.) |

#### Passage

A contiguous text span within a section. The atomic unit for extraction.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `text` | string | Yes | Raw passage text |
| `page` | integer | Yes | Source PDF page number (0-indexed) |
| `char_offset_start` | integer | No | Character offset start within page text |
| `char_offset_end` | integer | No | Character offset end within page text |
| `embedding` | list[float] | No | Vector embedding (optional, for RAG fallback) |
| `extraction_status` | string | No | "pending", "completed", "failed", "empty" |

#### ReferenceEntry

A single bibliographic reference cited in the document. Stored structurally for future citation linking.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `raw_text` | string | Yes | Full reference text as extracted |
| `order` | integer | Yes | Position in reference list (0-indexed) |
| `year` | integer | No | Extracted publication year |
| `title_guess` | string | No | Heuristic title extraction |
| `authors_guess` | list[string] | No | Heuristic author surnames |
| `citation_key_numeric` | integer | No | Numeric citation key (e.g., `3` for `[3]`) |
| `citation_key_author_year` | list[string] | No | Author-year keys (e.g., `vaswani:2017`) |

#### InlineCitation

A citation mention detected in a body passage.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `raw_text` | string | Yes | Raw inline mention text |
| `citation_style` | string | Yes | `numeric_bracket` or `author_year` |
| `start_char` | integer | Yes | Passage-local start offset |
| `end_char` | integer | Yes | Passage-local end offset |
| `page_number` | integer | Yes | Source page number |
| `reference_keys` | list[string] | No | Numeric keys extracted from mention |
| `reference_labels` | list[string] | No | Normalized author-year labels |

### Semantic Nodes

These represent extracted knowledge entities.

#### Author

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `canonical_name` | string | Yes | Normalized full name (e.g., "Ashish Vaswani") |
| `surface_forms` | list[string] | No | All observed name variants (e.g., ["A. Vaswani", "Vaswani, A."]) |

#### Institution

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `canonical_name` | string | Yes | Normalized name (e.g., "Google Brain") |
| `surface_forms` | list[string] | No | Observed variants |
| `type` | string | No | "university", "company", "lab", "government" |

#### Concept

A key technical term, theory, or abstraction discussed in the paper.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `canonical_name` | string | Yes | Normalized name (e.g., "Self-Attention") |
| `surface_forms` | list[string] | No | Observed variants (e.g., ["self-attention", "self attention mechanism"]) |
| `definition` | string | No | Extracted or summarized definition |

#### Method

A specific algorithm, model, or technique proposed or used.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `canonical_name` | string | Yes | Normalized name (e.g., "Transformer") |
| `surface_forms` | list[string] | No | Observed variants |
| `description` | string | No | Brief description of what the method does |

#### Dataset

A named dataset used for evaluation or training.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `canonical_name` | string | Yes | Normalized name (e.g., "WMT 2014 English-German") |
| `surface_forms` | list[string] | No | Observed variants |
| `domain` | string | No | Domain area (e.g., "machine translation", "image classification") |

#### Metric

A quantitative measure used to evaluate performance.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `canonical_name` | string | Yes | Normalized name (e.g., "BLEU") |
| `surface_forms` | list[string] | No | Observed variants (e.g., ["BLEU score", "BLEU-4"]) |

#### Task

A problem domain or application area.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `canonical_name` | string | Yes | Normalized name (e.g., "Machine Translation") |
| `surface_forms` | list[string] | No | Observed variants |

### Provenance Node

#### Evidence

Links a semantic relationship to its source passage. Every semantic edge must have at least one Evidence node.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `uid` | string (UUID) | Yes | Primary key |
| `passage_uid` | string | Yes | FK to Passage.uid |
| `document_uid` | string | Yes | FK to Document.uid |
| `confidence` | float | Yes | Extraction confidence (0.0 - 1.0) |
| `extraction_method` | string | Yes | e.g., "llm_gpt4o", "llm_llama70b", "rule_based", "manual" |
| `extracted_at` | datetime | Yes | Timestamp of extraction |
| `surface_text` | string | Yes | Exact text span from passage that supports this extraction |
| `citation_count` | integer | No | Number of inline citations in the source passage |
| `citation_labels` | list[string] | No | Citation labels detected in the source passage |

---

## Edge Types

### Structural Edges

These connect document structure nodes. They do not require provenance.

| Edge | Source | Target | Properties | Description |
|------|--------|--------|------------|-------------|
| `HAS_SECTION` | Document | Section | `ordinal: int` | Document contains this section |
| `HAS_PASSAGE` | Section | Passage | `ordinal: int` | Section contains this passage |
| `HAS_REFERENCE` | Document | ReferenceEntry | `order: int` | Document cites this reference |
| `HAS_INLINE_CITATION` | Passage | InlineCitation | — | Passage contains this inline citation mention |
| `REFERS_TO` | InlineCitation | ReferenceEntry | `confidence: float` | Inline citation linked to parsed reference entry |

### Semantic Edges

These represent extracted knowledge relationships. Every semantic edge carries an `evidence_uids` property linking to one or more Evidence nodes.

| Edge | Source | Target | Properties | Description |
|------|--------|--------|------------|-------------|
| `WROTE` | Author | Document | `evidence_uids: list[str]` | Author wrote this paper |
| `AFFILIATED_WITH` | Author | Institution | `evidence_uids: list[str]` | Author's affiliation at time of writing |
| `MENTIONS` | Document | Concept | `evidence_uids: list[str]` | Paper discusses this concept |
| `INTRODUCES` | Document | Method | `evidence_uids: list[str]` | Paper proposes or introduces this method |
| `USES` | Method | Dataset | `evidence_uids: list[str]` | Method is evaluated on this dataset |
| `USES` | Method | Method | `evidence_uids: list[str]` | Method builds upon or incorporates another method |
| `EVALUATED_ON` | Method | Task | `evidence_uids: list[str]` | Method is applied to this task |
| `MEASURED_BY` | Task | Metric | `evidence_uids: list[str]` | Task performance is measured by this metric |
| `ABOUT` | Document | Task | `evidence_uids: list[str]` | Paper addresses this task |

### Provenance Edges

These connect Evidence nodes to their source passages and identified entities.

| Edge | Source | Target | Properties | Description |
|------|--------|--------|------------|-------------|
| `FROM_PASSAGE` | Evidence | Passage | — | Evidence was extracted from this passage |
| `IDENTIFIES` | Evidence | (any semantic node) | — | Evidence identifies this entity |

---

## Provenance Model

The provenance chain enables full traceability:

```
RelationInstance
  └── Evidence node
        ├── confidence, extractor, citation_count, citation_labels
        ├── ─[FROM_PASSAGE]──> Passage
        │                     └── ─[HAS_INLINE_CITATION]──> InlineCitation
        │                                                └── ─[REFERS_TO]──> ReferenceEntry
        └── ─[belongs to]──> Section ──> Document
```

### Why Evidence as Separate Nodes?

1. A single semantic relationship may be supported by multiple passages — each gets its own Evidence node
2. Evidence nodes can be independently queried ("show all extractions from this passage")
3. Evidence metadata (method, timestamp, confidence) would bloat edge properties
4. Supports confidence aggregation across multiple sources
5. Enables extraction quality auditing and model comparison

---

## Example Records

### Creating a Document with Structure

```cypher
// Document
CREATE (d:Document {
  uid: "doc-001",
  title: "Attention Is All You Need",
  file_hash: "a1b2c3d4e5f6",
  file_name: "attention-is-all-you-need.pdf",
  year: 2017,
  created_at: datetime()
})

// Section
CREATE (s:Section {
  uid: "sec-001",
  title: "3. Model Architecture",
  ordinal: 2,
  level: 1
})
CREATE (d)-[:HAS_SECTION {ordinal: 2}]->(s)

// Passage
CREATE (p:Passage {
  uid: "pass-001",
  text: "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
  page: 2,
  extraction_status: "completed"
})
CREATE (s)-[:HAS_PASSAGE {ordinal: 0}]->(p)
```

### Extracting an Entity with Evidence

```cypher
// Method entity
MERGE (m:Method {canonical_name: "Transformer"})
  ON CREATE SET m.uid = "meth-001", m.surface_forms = ["Transformer"]
  ON MATCH SET m.surface_forms =
    CASE WHEN NOT "Transformer" IN m.surface_forms
         THEN m.surface_forms + "Transformer"
         ELSE m.surface_forms END

// Semantic edge with provenance
MATCH (d:Document {uid: "doc-001"})
MERGE (d)-[r:INTRODUCES]->(m)
  ON CREATE SET r.evidence_uids = ["ev-001"]
  ON MATCH SET r.evidence_uids =
    CASE WHEN NOT "ev-001" IN r.evidence_uids
         THEN r.evidence_uids + "ev-001"
         ELSE r.evidence_uids END

// Evidence node
CREATE (e:Evidence {
  uid: "ev-001",
  passage_uid: "pass-001",
  document_uid: "doc-001",
  confidence: 0.95,
  extraction_method: "llm_gpt4o",
  extracted_at: datetime(),
  surface_text: "We propose a new simple network architecture, the Transformer"
})

// Provenance links
MATCH (p:Passage {uid: "pass-001"})
CREATE (e)-[:FROM_PASSAGE]->(p)
CREATE (e)-[:IDENTIFIES]->(m)
```

### Querying with Provenance

```cypher
// Find all methods introduced in a document, with evidence
MATCH (d:Document {uid: "doc-001"})-[r:INTRODUCES]->(m:Method)
UNWIND r.evidence_uids AS ev_uid
MATCH (e:Evidence {uid: ev_uid})-[:FROM_PASSAGE]->(p:Passage)
RETURN m.canonical_name AS method,
       e.confidence AS confidence,
       e.surface_text AS evidence,
       p.page AS page
ORDER BY e.confidence DESC
```

---

## V1 Exclusions

The following types are intentionally excluded from V1:

| Type | Reason |
|------|--------|
| **CitedWork / CrossDocumentCitation** | Requires cross-document entity resolution. Sprint 6 stores inline citation structure and links to local `ReferenceEntry`, but does not resolve cited work as first-class document nodes. Deferred to V2. |
| **Venue / Conference** | Low extraction reliability from body text. Typically requires metadata parsing (PDF headers, DOI lookup), not passage extraction. |
| **Figure / Table** | Requires multimodal extraction capabilities. Out of scope for a text-only pipeline. |
| **Result** (numerical) | Structured extraction of experimental results from tables is unreliable with current LLM approaches. Deferred to V2. |
| **Claim / Hypothesis** | Too subjective for reliable extraction. "This paper claims X" is hard to distinguish from "This paper mentions X" without deep reasoning. |
| **Date** | Publication dates come from metadata, not passage extraction. Can be stored as Document.year. |

---

## Ontology Evolution

This ontology is designed to grow. V2 candidates:

- `CitedWork` node + cross-document `CITES` edge
- `Result` node with structured numeric values
- `Venue` node (conference/journal metadata)
- `Claim` node with `SUPPORTS` / `CONTRADICTS` edges
- `Figure` node (with multimodal extraction)

Any ontology change must update this document first, then propagate to extraction prompts, schema validators, and graph storage constraints.
