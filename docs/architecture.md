# Mimari — Canonical Referans (Sprint 23)

## Primary Runtime Path
```
PDF → parse → LLM extract → normalize → Neo4j write → semantic query
```

## API Endpoints (aktif)
| Endpoint | Dosya | Durum |
|----------|-------|-------|
| `POST /api/ingest` | `api/ingest.py` | Primary |
| `GET /api/ingest/{job_id}` | `api/ingest.py` | Primary |
| `GET /api/graph/semantic` | `api/graph.py` | Primary |
| `GET /api/graph/node/{id}` | `api/graph.py` | Primary |
| `POST /api/query/semantic` | `api/query.py` | Primary |
| `POST /api/extract` | `api/extract.py` | Diagnostik |

## Graph Modeli — DOĞRU PATTERN (reified)
```
(source)-[:OUT_REL]->(RelationInstance)-[:TO]->(target)
(Evidence)-[:SUPPORTS]->(RelationInstance)
(Evidence)-[:FROM_PASSAGE]->(Passage)
(CanonicalEntity)<-[:INSTANCE_OF_CANONICAL]-(Concept|Method|...)
```

Doğru referans: docs/graph_contract.md

## Node Tipleri (ontology_v1 + Sprint 19+)
- Semantic: Concept, Method, Dataset, Metric, Task, Author, Institution
- Canonical: CanonicalEntity (Sprint 19'da eklendi, ontology_v1'de henüz yok)
- Reified: RelationInstance
- Provenance: Evidence, Passage, Section, Document
- Citation: InlineCitation, ReferenceEntry

## Servis Katmanları

### Ingestion Pipeline
```
SemanticIngestionService
  → DocumentParser → PassageSplitter → SectionDetector
  → LLMExtractor → ExtractionPipeline
  → EntityNormalizer → RelationNormalizer → CanonicalNormalizer → EntityLinker
  → GraphWriter
      → DocumentWriter, EntityWriter, RelationWriter
      → CitationWriter, CanonicalWriter
```

### Query Pipeline V2 (Sprint 21+)
```
SemanticQueryService
  → QuestionInterpreter
  → CandidateSelector (canonical-aware)
  → TraversalPlanner → TraversalExecutor
  → SemanticQueryReader / SemanticGraphReader
  → EvidenceRanker → EvidenceClusterer
  → InsightBuilder
  → AnswerComposer → ExplanationBuilder
```

## Deterministic ID'ler
- Entity: type:slug(canonical_name)
- Relation: ri:relType:sourceUid:targetUid
- Evidence: ev:{ri_uid}:{passage_id}

## Dokunma Listesi
- backend/app/legacy/ — quarantine, dokunma
- frontend/app/legacy/ — quarantine, dokunma
- domain/identity.py — ID mantığı, kırılırsa graph bozulur
- schemas/ — API contract, değişirse frontend çöker
