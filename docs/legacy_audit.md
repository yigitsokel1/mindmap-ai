# MindMap-AI: Legacy Code Audit

This document classifies every existing file in the repository by its fate in the architectural pivot from chunk/embedding RAG to Semantic Knowledge Graph Extraction.

**Version:** 1.1 (updated Sprint 4)
**Status:** Active
**Depends on:** `ontology_v1.md`, `extraction_contract.md`, `graph_storage_model.md`

---

## Classification Legend

| Status | Meaning |
|--------|---------|
| **KEEP** | File is reusable as-is or with minor adjustments (< 20% change) |
| **REFACTOR** | File's concept is valuable but implementation must be substantially rewritten (> 50% change) |
| **DELETE** | File is replaced by a new equivalent or is no longer needed |
| **UPDATE** | Documentation file that needs content revision |

---

## Backend Audit

### `backend/app/main.py` — **KEEP**

**Lines:** ~80
**What it does:** FastAPI app creation, CORS middleware, lifespan (Neo4j connect/disconnect), static file mount, router inclusion.
**Why keep:** The FastAPI skeleton, CORS config, lifespan pattern, and static file mount are all directly reusable. This is infrastructure code, not domain logic.
**Changes needed:**
- Add new routers: `api/query.py`, `api/graph.py`, `api/extraction_status.py`
- Update app metadata (title → "MindMap-AI Semantic KG API", version → "0.2.0")
- Add `schema_init.run()` call in lifespan startup (to create Neo4j constraints)
- Keep existing `/api/ingest` router

---

### `backend/app/api/endpoints.py` — **REFACTOR**

**Lines:** ~643
**What it does:** Handles `/chat`, `/ingest`, `/graph` in a single monolithic file. Contains 30+ `print()` debug statements. The `/graph` endpoint is ~460 lines of procedural Neo4j record processing hardcoded for Document/Chunk node types.
**Why refactor:** Three concerns in one file. Debug logging via `print()`. Hardcoded for 2 node types (needs 10+). Pydantic models mixed with route logic.

**Split plan:**

| New file | From existing | Purpose |
|----------|---------------|---------|
| `api/ingest.py` | `/ingest` endpoint + file upload logic | Upload PDF, trigger pipeline |
| `api/query.py` | `/chat` endpoint (rewritten) | NL question → Cypher → answer with provenance |
| `api/graph.py` | `/graph` endpoint (rewritten) | Graph visualization data for all 10+ node types |
| `api/extraction_status.py` | New | Extraction progress per document |
| `schemas/requests.py` | `ChatRequest`, `IngestRequest` models | Pydantic request models |
| `schemas/responses.py` | Inline response dicts | Pydantic response models |

**What to keep from this file:**
- The file upload / temp file / cleanup pattern in `/ingest`
- The `ChatRequest` model shape (adapt for new query interface)
- CORS and error handling patterns

**What to delete:**
- All `print()` statements (replace with `loguru`)
- The 460-line `/graph` endpoint (rewrite for new schema)
- `IngestRequest` model (legacy path-based ingestion)
- Fallback query logic

---

### `backend/app/core/db.py` — **KEEP**

**Lines:** ~133
**What it does:** Singleton `Neo4jDatabase` class with connect/verify/close/driver.
**Why keep:** Clean singleton pattern. Connection management is database-agnostic — doesn't care what node types exist.
**Changes needed:**
- Add `execute_query(cypher, params)` method with retry logic
- Add `run_schema_init()` method to execute constraint DDL from `graph_storage_model.md`
- Consider async driver support (currently sync) — not blocking for Sprint 2

---

### `backend/app/services/ingestion.py` — **REFACTOR**

**Lines:** ~344
**What it does:** PDF loading (PyPDFLoader) → chunking (RecursiveCharacterTextSplitter, 1000/200) → embedding (OpenAI) → Neo4j storage (Document + Chunk nodes).
**Why refactor:** This is the core of the old architecture. Every step except file hashing and duplicate detection is chunk-centric and must be replaced.

**Decomposition plan:**

| New module | Replaces | Purpose |
|------------|----------|---------|
| `services/parsing/pdf_parser.py` | PyPDFLoader usage | PDF → pages with text and metadata |
| `services/parsing/section_detector.py` | (new) | Detect section headings, assign levels |
| `services/parsing/passage_segmenter.py` | RecursiveCharacterTextSplitter | Split sections into 500-2000 char passages |
| `services/extraction/llm_extractor.py` | (new) | Send passage to LLM, get entity/relation JSON |
| `services/normalization/entity_resolver.py` | (new) | Deduplicate entities by canonical_name |
| `services/graph/graph_writer.py` | `_store_document_and_chunks()` | Write typed nodes + edges + evidence to Neo4j |
| `services/orchestrator.py` | `ingest_pdf()` top-level | Coordinate parse → extract → normalize → store |

**What to keep:**
- `_calculate_file_hash()` — MD5 hashing for dedup (move to `services/parsing/pdf_parser.py`)
- `_check_duplicate()` — Cypher dedup check (move to `repositories/document_repo.py`)
- `uploaded_docs/` directory pattern

**What to delete:**
- `RecursiveCharacterTextSplitter` usage (replaced by section-aware segmentation)
- `OpenAIEmbeddings` as primary pipeline step (embeddings become optional)
- `_store_document_and_chunks()` (replaced by typed graph writer)
- Chunk-based Neo4j Cypher queries

---

### `backend/app/services/retrieval.py` — **REFACTOR**

**Lines:** ~659
**What it does:** Vector cosine similarity search on Chunk embeddings → LLM context building → Groq answer generation. Has fallback manual cosine similarity in Python. Also has GraphCypherQAChain path (rarely used).
**Why refactor:** Entirely built around the chunk/embedding model. In the new system, graph query (Cypher) is primary; vector search is optional fallback.

**Decomposition plan:**

| New module | Replaces | Purpose |
|------------|----------|---------|
| `services/query/cypher_generator.py` | GraphCypherQAChain | NL → Cypher using new schema-aware prompts |
| `services/query/context_assembler.py` | `_build_context_with_citations()` | Gather Evidence/Passage data for LLM context |
| `services/query/answer_generator.py` | LLM invoke logic | Generate answer with provenance citations |

**What to keep:**
- Groq/ChatGroq integration pattern (LLM client setup, temperature config)
- The concept of building context with citations (adapt for Evidence-based provenance)

**What to delete:**
- `_vector_search_chunks()` and `_vector_search_chunks_manual()` — chunk-based vector search
- Manual Python cosine similarity implementation
- GraphCypherQAChain with old schema prompt
- Neighborhood search Cypher (references old node types)
- Neo4jGraph LangChain wrapper (use direct driver instead)

---

## Frontend Audit

### `frontend/app/components/GraphViewer3D.tsx` — **REFACTOR**

**Lines:** ~1237
**What it does:** 3D force-directed graph visualization with react-force-graph-3d. Handles 2 node types (Document: pink, Chunk: cyan) with hardcoded colors/sizes. Features starfield background, glow effects, camera animations.
**Why refactor:** Visual infrastructure is excellent. But the node rendering logic only handles 2 types and must support 10.

**Changes needed:**
- Add node type → color/size/shape mapping for all 10 semantic types + Evidence
- Remove Chunk-specific rendering logic
- Add edge type labels on links
- Update node tooltip/label to show `canonical_name` for semantic nodes
- Consider splitting: core renderer vs. visual config vs. camera controls

**What to keep:**
- react-force-graph-3d setup and force simulation config
- Starfield background animation
- Glow texture and node sprite rendering
- Camera animation system (focus, orbit, easing)
- Graph data fetching pattern

---

### `frontend/app/components/CommandCenter.tsx` — **KEEP**

**Lines:** ~269
**What it does:** Left panel with Chat and Files tabs. Handles chat messages and file upload UI.
**Changes needed:**
- Update chat API call: new endpoint format, new response shape
- Display Evidence-based citations (passage text + confidence + section) instead of chunk-based ones
- Add extraction progress indicator when uploading

---

### `frontend/app/components/FileLibrary.tsx` — **KEEP**

**Lines:** ~194
**What it does:** Document upload form with drag-and-drop, upload progress, document listing.
**Changes needed:**
- Display extraction stats in upload result (entity count, relation count, avg confidence)
- Show extraction status per document ("extracting...", "completed", "failed")

---

### `frontend/app/components/Inspector.tsx` — **KEEP**

**Lines:** ~67
**What it does:** Right panel PDF viewer using react-pdf.
**Changes needed:**
- Add node detail panel: when a graph node is selected, show its properties, connected edges, and evidence passages
- Keep PDF viewing for provenance drill-down (click evidence → jump to page)

---

### `frontend/app/components/ChatBubble.tsx` — **KEEP**

**Lines:** ~56
**What it does:** Renders individual chat messages with markdown-like styling.
**Changes needed:** None. Generic enough to work with new response format.

---

### `frontend/app/components/CitationChip.tsx` — **KEEP**

**Lines:** ~30
**What it does:** Small chip showing doc_name + page number for citations.
**Changes needed:**
- Add confidence score display (e.g., "95%")
- Add section title
- Clicking should show evidence passage text

---

### `frontend/app/components/StatusBar.tsx` — **KEEP**

**Lines:** ~78
**What it does:** Bottom bar showing system health (API, Neo4j status via polling).
**Changes needed:**
- Add extraction pipeline status indicator
- Show entity/relation counts from graph

---

### `frontend/app/store/useAppStore.ts` — **KEEP**

**Lines:** ~63
**What it does:** Zustand state store with UI state (panels, tabs, PDF viewer, graph highlighting).
**Changes needed:**
- Add `selectedNodeDetails` state (for Inspector node detail panel)
- Add `nodeTypeFilters` state (filter graph by entity type)
- Add `extractionStatus` state per document

---

### `frontend/app/lib/types.ts` — **REFACTOR**

**Lines:** ~47
**What it does:** TypeScript interfaces for GraphNode, GraphLink, Document, ChatMessage, ChatSource.
**Why refactor:** Current types only cover 2 node types. Needs interfaces for all 10 + Evidence + new response formats.
**Changes needed:**
- Add typed interfaces for each node type (AuthorNode, MethodNode, etc.)
- Add `EvidenceSource` type
- Add `ExtractionResult` type
- Add `QueryResponse` type with provenance
- `GraphNode` becomes a union type or uses a `nodeType` discriminator

---

### `frontend/app/lib/constants.ts` — **KEEP**

**Lines:** ~13
**What it does:** API endpoint URL constants.
**Changes needed:**
- Add `/api/query` endpoint
- Add `/api/extraction/{doc_uid}` endpoint
- Rename `/api/chat` → `/api/query` (or keep both during transition)

---

### `frontend/app/globals.css` — **KEEP**

Tailwind config + custom animations. No domain logic.

---

### `frontend/app/layout.tsx` — **KEEP**

Root layout wrapper. No domain logic.

---

### `frontend/app/page.tsx` — **KEEP**

Main page composing GraphViewer3D + CommandCenter + Inspector + StatusBar. Layout changes only if new panels are added.

---

## Documentation Audit

### `docs/graph_schema.md` — **DELETE**

**Reason:** Defines Paper, Author, Institution, Concept nodes that were never implemented. Fully superseded by `docs/ontology_v1.md` which has a more comprehensive and extraction-oriented schema.

---

### `docs/project_charter.md` — **UPDATE**

**Reason:** Still valid as project context. Needs revision to reflect:
- Pivot from RAG-centric to KG-extraction-centric
- New Phase 2 definition (extraction pipeline, not just "optimization")
- Updated success metrics (extraction quality, not just query speed)

---

## Root-Level Files

### `run_ingest.py` — **REFACTOR**

Manual ingestion script. Needs to call new orchestrator instead of old IngestionService.

### `pyproject.toml` — **UPDATE**

Add new dependencies:
- `jsonschema` — extraction output validation
- Potentially remove `langchain-experimental` if GraphCypherQAChain is dropped

### `.env.example` / `env.example` — **KEEP**

Environment variables remain the same (Neo4j, Groq, OpenAI).

### `README.md` — **UPDATE**

Must reflect new architecture, setup, and usage after Sprint 2+.

---

## Target Backend Folder Structure

```
backend/app/
  __init__.py
  main.py                              # KEEP — FastAPI app, lifespan, CORS

  api/
    __init__.py
    ingest.py                           # FROM endpoints.py /ingest — file upload + pipeline trigger
    query.py                            # NEW — NL question → Cypher → answer with provenance
    graph.py                            # FROM endpoints.py /graph — visualization data (10+ node types)
    extraction_status.py                # NEW — extraction progress per document

  core/
    __init__.py
    db.py                               # KEEP — Neo4j singleton connection
    config.py                           # NEW — Pydantic Settings for env vars, model configs
    schema_init.py                      # NEW — Run constraint DDL from graph_storage_model.md

  domain/
    __init__.py
    ontology.py                         # NEW — Python enums for node/edge types (single source of truth)

  services/
    __init__.py
    orchestrator.py                     # NEW — parse → extract → normalize → store coordinator

    parsing/
      __init__.py
      pdf_parser.py                     # FROM ingestion.py — PDF → pages with metadata
      section_detector.py               # NEW — detect section headings, assign levels
      passage_segmenter.py              # NEW — section → passages (replaces RecursiveCharacterTextSplitter)

    extraction/
      __init__.py
      llm_extractor.py                  # NEW — passage → LLM → entity/relation JSON
      prompt_templates.py               # NEW — system prompt, extraction prompt, fix-JSON prompt
      schema_validator.py               # NEW — jsonschema validation of LLM output
      output_parser.py                  # NEW — parse validated JSON → domain objects

    normalization/
      __init__.py
      entity_resolver.py               # NEW — deduplicate entities by canonical_name
      alias_manager.py                  # NEW — track and merge surface_forms
      confidence_aggregator.py          # NEW — aggregate confidence across evidence sources

    graph/
      __init__.py
      graph_writer.py                   # FROM ingestion.py — write entities, relations, evidence to Neo4j
      graph_reader.py                   # FROM endpoints.py /graph — read graph data for visualization
      provenance_linker.py              # NEW — create Evidence nodes + FROM_PASSAGE edges

    query/
      __init__.py
      cypher_generator.py               # FROM retrieval.py — NL → Cypher (new schema-aware prompts)
      context_assembler.py              # FROM retrieval.py — gather evidence/passages for LLM context
      answer_generator.py               # FROM retrieval.py — LLM answer generation with citations

  repositories/
    __init__.py
    document_repo.py                    # NEW — CRUD for Document nodes
    entity_repo.py                      # NEW — CRUD for semantic entity nodes
    evidence_repo.py                    # NEW — CRUD for Evidence nodes
    passage_repo.py                     # NEW — CRUD for Passage/Section nodes

  schemas/
    __init__.py
    requests.py                         # FROM endpoints.py — Pydantic request models
    responses.py                        # FROM endpoints.py — Pydantic response models
    extraction.py                       # NEW — Pydantic models matching extraction JSON schema
    graph_viz.py                        # NEW — Pydantic models for graph visualization data
```

### Module Responsibilities

| Module | Responsibility | Calls |
|--------|---------------|-------|
| `orchestrator.py` | Pipeline coordinator. Entry point for ingestion. | parsing → extraction → normalization → graph |
| `services/parsing/` | Stateless PDF → structured passages. No LLM, no DB. | — |
| `services/extraction/` | LLM interaction for entity/relation extraction. Retries, validation. | LLM API |
| `services/normalization/` | Post-extraction dedup. String similarity + optional LLM assist. | — |
| `services/graph/` | All Neo4j writes for the knowledge graph. MERGE for entities, CREATE for evidence. | Neo4j driver |
| `services/query/` | Handle user questions. Cypher generation + context + answer. | Neo4j driver, LLM API |
| `repositories/` | Thin Cypher query wrappers. One repo per node family. | Neo4j driver |
| `schemas/` | Pydantic models for API + extraction validation. | — |

---

## Migration Strategy

### Phase 1 (Sprint 2): Parallel Operation

- New pipeline writes new node types alongside old Chunk nodes
- Old endpoints remain functional during transition
- Frontend can toggle between old graph view and new semantic graph

### Phase 2 (Sprint 3+): Cutover

- Old `/chat` endpoint deprecated, replaced by `/query`
- Old `/graph` endpoint updated to serve only semantic nodes
- Chunk nodes and BELONGS_TO edges removed from database
- Legacy code files deleted

### No Big Bang

The migration is incremental. At no point should the system be completely broken. Each sprint delivers a working (if incomplete) system.

---

## Sprint 4 Status Update

As of Sprint 4, the semantic ingestion path is **primary**:

- `POST /api/ingest` defaults to `mode=semantic` (SemanticIngestionService)
- Legacy chunk/embedding path available via `mode=legacy` query param
- `backend/app/services/ingestion.py` is now **LEGACY** — kept for backward compatibility only
- `backend/app/services/ingestion/semantic_ingestion_service.py` is the **PRIMARY** ingestion path

**New files created in Sprints 2-4:**

| File | Purpose | Sprint |
|------|---------|--------|
| `backend/app/schemas/entities.py` | Entity Pydantic models | 2 |
| `backend/app/schemas/relations.py` | Relation Pydantic models | 2 |
| `backend/app/schemas/extraction.py` | ExtractionResult model | 2 |
| `backend/app/schemas/passage.py` | PassageRecord with page provenance | 3, extended 4 |
| `backend/app/domain/identity.py` | Entity UID generation | 3 |
| `backend/app/services/parsing/passage_splitter.py` | Text → passages | 2 |
| `backend/app/services/parsing/pdf_parser.py` | PDF → PageRecords | 4 |
| `backend/app/services/parsing/document_parser.py` | PDF → page-aware PassageRecords | 4 |
| `backend/app/services/extraction/llm_extractor.py` | LLM entity/relation extraction | 2 |
| `backend/app/services/extraction/pipeline.py` | Extraction orchestrator | 2, refactored 3-4 |
| `backend/app/services/normalization/entity_normalizer.py` | Name cleaning, dedup, confidence gate | 3 |
| `backend/app/services/normalization/relation_normalizer.py` | Type-triple validation, self-loop drop | 3 |
| `backend/app/services/graph/graph_writer.py` | Neo4j writer with provenance | 2, rewritten 3-4 |
| `backend/app/services/ingestion/semantic_ingestion_service.py` | Primary ingestion service | 4 |

---

## Sprint 7 Status Update

As of Sprint 7, read paths are explicitly separated:

- `GET /api/graph/semantic` is the only supported semantic graph read path.
- `GET /api/graph/legacy` keeps legacy Document/Chunk visualization behavior.
- Semantic graph response contract is standardized in `backend/app/schemas/graph_response.py`.
- `POST /api/chat` is explicitly marked as legacy retrieval path (semantic chat pending).
- Legacy retrieval is namespaced under `backend/app/services/legacy/`.

Runtime truth table after Sprint 7:

| Capability | Primary Path | Migration/Fallback Path |
|------------|--------------|-------------------------|
| Ingestion | `POST /api/ingest?mode=semantic` | `POST /api/ingest?mode=legacy` |
| Graph Read | `GET /api/graph/semantic` | `GET /api/graph/legacy` |
| Chat | pending semantic chat | `POST /api/chat` (legacy retrieval) |

---

## Sprint 8 Status Update

As of Sprint 8, backend quality gates and test coverage were expanded for semantic KG critical paths:

- `backend/tests/unit/` now covers identity UIDs, entity/relation normalization, section/reference/inline-citation/document parsing, and semantic graph reader shaping.
- `backend/tests/integration/` now includes contract tests for:
  - `POST /api/extract` diagnostics response
  - `GET /api/graph/semantic` empty graph contract and `node_types` parsing (CSV + repeated params)
- `backend/tests/fixtures/` includes compact academic/parsing/citation/reference samples for deterministic tests.
- Local baseline quality gate commands are standardized:
  - `poetry run pytest backend/tests`
  - `poetry run python -m compileall backend/app`

---

## Sprint 10 Status Update

As of Sprint 10, semantic QA/query path is implemented as a dedicated grounded endpoint:

- `POST /api/query/semantic` is added as a semantic graph-backed query contract.
- Response contract is evidence-first (`answer`, `evidence`, `related_nodes`, `citations`, `confidence`, `mode`).
- `POST /api/chat` remains available as legacy retrieval mode for compatibility.
- Command Center includes explicit `Legacy Chat` vs `Semantic Query` user mode split.
- Backend tests now include semantic query service unit coverage and endpoint contract checks.

Runtime truth table after Sprint 10:

| Capability | Primary Path | Migration/Fallback Path |
|------------|--------------|-------------------------|
| Ingestion | `POST /api/ingest?mode=semantic` | `POST /api/ingest?mode=legacy` |
| Graph Read | `GET /api/graph/semantic` | `GET /api/graph/legacy` |
| Query/QA | `POST /api/query/semantic` | `POST /api/chat` (legacy retrieval) |

---

## Summary Table

| File | Status | Priority | Sprint |
|------|--------|----------|--------|
| `backend/app/main.py` | KEEP | Low | 2 |
| `backend/app/api/endpoints.py` | REFACTOR (shim after split) | High | 2, updated 4, split 7 |
| `backend/app/core/db.py` | KEEP | Low | 2 |
| `backend/app/services/ingestion.py` | **LEGACY** | Low | — (kept for fallback) |
| `backend/app/services/retrieval.py` | **LEGACY CORE (compat)** | High | isolated 7 |
| `backend/app/services/legacy/retrieval.py` | KEEP (legacy namespace) | High | 7 |
| `frontend/app/components/GraphViewer3D.tsx` | REFACTOR | Medium | future |
| `frontend/app/components/CommandCenter.tsx` | KEEP | Low | future |
| `frontend/app/components/FileLibrary.tsx` | KEEP | Low | future |
| `frontend/app/components/Inspector.tsx` | KEEP | Low | future |
| `frontend/app/store/useAppStore.ts` | KEEP | Low | future |
| `frontend/app/lib/types.ts` | REFACTOR | Medium | future |
| `docs/graph_schema.md` | DELETE | Immediate | 1 |
| `docs/project_charter.md` | UPDATE | Low | future |
