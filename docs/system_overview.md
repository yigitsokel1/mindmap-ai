# MindMap-AI Canonical System Overview

## Purpose
MindMap-AI extracts semantic entities, relations, and provenance from documents, stores them in Neo4j, and serves grounded query answers plus graph/inspector experiences.

This overview is the canonical runtime reference after Sprint 24 delivery (canonical linking, evidence clustering, insight synthesis, frontend interaction refresh, test coverage uplift, and hallucination guard).

## Core Layers
- **API Layer**: request validation and transport (`/api/ingest`, `/api/query/semantic`, `/api/graph/semantic`, `/api/graph/node/{id}`).
- **Service Orchestration Layer**:
  - Ingestion orchestration in `semantic_ingestion_service`.
  - Query orchestration in `SemanticQueryService`.
- **Reader/Writer Layer**:
  - Writes through `GraphWriter` facade and writer modules.
  - Reads through semantic graph/query readers.
- **Domain + Schema Layer**:
  - deterministic identity in `domain/identity.py`
  - typed contracts in `schemas/`.
- **Storage Layer**: Neo4j graph model for semantic/runtime nodes and edges.

## Active Runtime Surface
- **Primary write paths**
  - `POST /api/ingest` (semantic mode)
  - Graph writes via `GraphWriter` -> `DocumentStructureWriter`, `EntityWriter`, `RelationWriter`, `CitationWriter`.
- **Primary read/query paths**
  - `GET /api/graph/semantic`
  - `GET /api/graph/node/{id}`
  - `POST /api/query/semantic`

Deprecated alias endpoints can remain for compatibility, but new consumers must use canonical paths above.

## Graph Model Summary
- **Semantic nodes**: `Concept`, `Method`, `Dataset`, `Metric`, `Task`, `Author`, `Institution`.
- **Reified relation node**: `RelationInstance`.
- **Provenance nodes**: `Evidence`, `Passage`, `Section`, `Document`.
- **Citation nodes**: `InlineCitation`, `ReferenceEntry`.
- **Core relation pattern**:
  - `(source)-[:OUT_REL]->(RelationInstance)-[:TO]->(target)`
  - `(Evidence)-[:SUPPORTS]->(RelationInstance)`
  - `(Evidence)-[:FROM_PASSAGE]->(Passage)`

Deterministic IDs:
- entity UID: `type:slug(canonical_name)`
- relation UID: `ri:relType:sourceUid:targetUid`
- evidence UID default: `ev:{ri_uid}:{passage_id}`

## Query Pipeline Summary
1. `SemanticQueryService` interprets question intent.
2. `CandidateSelector` asks `SemanticQueryReader` for candidate entities.
3. `TraversalPlanner` decides traversal/evidence budget.
4. `SemanticQueryReader` collects evidence records.
5. `EvidenceRanker` scores and ranks.
6. `EvidenceClusterer` groups evidence around stable relation/entity patterns.
7. `InsightBuilder` derives reusable high-confidence insights from clusters.
8. `AnswerComposer` shapes answer text + guardrails.
9. `ExplanationBuilder` assembles reasoning metadata.
10. Response returns matched entities, clustered evidence, insights, citations, and confidence metadata.

## Legacy Quarantine
- Legacy ingestion/retrieval compatibility paths remain isolated under legacy namespaces and compatibility routers.
- `/api/graph` alias is compatibility-only; canonical clients should call:
  - `/api/graph/semantic`
  - `/api/graph/node/{id}`
- Frontend alias constant removed from active usage to reduce accidental regressions.

## Eval and Test Strategy
- **Backend**: unit + integration tests for graph write/query contracts.
- **Frontend**: vitest for command center/inspector flows.
- **Eval runner**: semantic quality and grounded-answer checks.
- **Smoke checks**: semantic query, node detail, citation/provenance navigation.

Latest verification snapshot (2026-04-27, Sprint 24):
- Backend tests: pass (`93 passed`).
- Frontend unit tests: pass (`4 passed`).
- Frontend e2e smoke: pass (`6 passed`).
- Semantic eval: intent accuracy `100%`, evidence presence `100%`, hallucination rate `0%`.

## Sprint 23-24 Delivery Notes

- **Sprint 23 (Schema sync + cleanup)**:
  - `NodeDetail.metadata` ve `SemanticEvidenceItem.cluster_key` backend schema'ya ve frontend tiplerine eklendi.
  - Legacy tsx bileşenleri (`GraphViewer3D`, `ChatBubble`) ve dead constant (`API_ENDPOINTS.DOCUMENTS`) kaldırıldı.
  - `QuestionInterpreter._detect_intent` fix: 5 yanlış sınıflandırma düzeltildi (intent accuracy 73%→100%).
  - `docs/graph_storage_model.md`, `docs/ontology_v1.md`, `docs/system_overview.md` reified pattern'e göre güncellendi.
- **Sprint 24 (Test coverage + hallucination guard)**:
  - Extraction pipeline (`llm_extractor`, `extraction_pipeline`, `semantic_ingestion_service`), `QuestionInterpreter`, `AnswerComposer` için unit testler yazıldı (93 passed).
  - `should_not_answer` guard `SemanticQueryService`'e eklendi; hallucination rate `100%→0%`.
  - Demo path production ortamında doğrulandı.

## Sprint 19-22 Delivery Notes
- **Sprint 19 (Canonical linking live)**:
  - Canonical linking is active in candidate resolution and graph writes (`CanonicalEntity` + linker/writer flow).
  - Candidate source semantics are stable (`local`, `canonical-ready`, `alias`) and consumed by query orchestration.
- **Sprint 20 (Compatibility cleanup)**:
  - Compatibility-only surfaces were reduced; canonical API paths remain the primary client contract.
  - Dead/duplicate frontend endpoint constants and legacy-facing usage were trimmed from active paths.
- **Sprint 21 (Grounding quality uplift)**:
  - Evidence clustering + insight synthesis were added to the query pipeline.
  - Response contract now supports `clusters`, `insights`, and richer uncertainty signaling.
- **Sprint 22 (Product readiness UI pass)**:
  - Command center, inspector, and semantic graph interaction loops were streamlined around:
    - source-first answer display,
    - inspector node detail drill-down,
    - graph focus/highlight synchronization from query results.

## Frontend Runtime Interaction (Sprint 22)
- `CommandCenter` drives semantic query submission and receives grounded response payloads.
- Query results set graph focus seeds and highlighted nodes through shared store state.
- `SemanticGraphViewer` uses this focus model to bias camera/selection and scoped rendering.
- `Inspector` resolves node detail (`/api/graph/node/{id}`), surfaces summaries/metadata, and opens source PDF context when available.
