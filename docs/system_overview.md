# MindMap-AI Canonical System Overview

## Purpose
MindMap-AI extracts semantic entities, relations, and provenance from documents, stores them in Neo4j, and serves grounded query answers plus graph/inspector experiences.

This overview is the single canonical reference for runtime architecture before Sprint 19 cross-document canonical linking.

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
6. `AnswerComposer` shapes answer text + guardrails.
7. `ExplanationBuilder` assembles reasoning metadata.
8. Response is returned with matched entities, evidence, citations, and confidence.

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

## Canonical Linking Direction (Sprint 19)
- Add canonical lookup reads behind reader contracts (`read_canonical_lookup_candidates` and query-reader lookup hooks).
- Extend `CandidateEntity` source semantics (`local`, `canonical-ready`, `alias`) without changing API response shape.
- Keep `SemanticQueryService` orchestration-only while canonical resolution/scoring evolves in selector/reader modules.
- Keep writer interfaces stable so canonical link writes can target dedicated writers without re-centralizing `GraphWriter`.
