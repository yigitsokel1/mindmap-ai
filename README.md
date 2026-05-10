# MindMap-AI — Semantic Research Copilot

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![Three.js](https://img.shields.io/badge/Three.js-000000?style=for-the-badge&logo=threedotjs&logoColor=white)

Upload academic PDFs, explore their knowledge as a 3D semantic graph, and get evidence-backed answers grounded in the document graph — not hallucinated summaries.

**Live demo:** [https://frontend-kappa-rosy-63.vercel.app](https://frontend-kappa-rosy-63.vercel.app)

---

## What It Does

1. **Ingest** — Upload a PDF. The pipeline parses it, extracts typed entities and relations via LLM, normalizes them to a canonical graph, and persists everything to Neo4j.
2. **Explore** — An interactive 3D force-graph renders the knowledge graph. Nodes are entities (Method, Concept, Dataset, Author…); edges are typed relations. Click a node to inspect its evidence, citations, and canonical links.
3. **Query** — Ask a question. The semantic query pipeline traverses the graph, collects evidence passages, ranks them, and composes a grounded answer with citation chips and PDF page jumps.
4. **Read** — Click a citation to open the source PDF at the exact page, with the relevant passage highlighted.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Llama-3.3-70b via Groq API |
| **Embeddings** | OpenAI text-embedding-3-small |
| **Graph DB** | Neo4j (AuraDB in production) |
| **Backend** | FastAPI + LangChain + Poetry |
| **Frontend** | Next.js 16, React 19, Zustand |
| **3D Graph** | Three.js + react-force-graph-3d |
| **PDF Viewer** | react-pdf v9 with text-layer highlight |
| **Deploy** | Render (backend) + Vercel (frontend) |

---

## Architecture

```
PDF → DocumentParser → PassageSplitter → SectionDetector
    → LLMExtractor → ExtractionPipeline
    → EntityNormalizer → RelationNormalizer → CanonicalNormalizer → EntityLinker
    → GraphWriter → Neo4j

Query → QuestionInterpreter → CandidateSelector → TraversalPlanner
      → SemanticQueryReader → EvidenceRanker → EvidenceClusterer
      → InsightBuilder → AnswerComposer
```

Graph model uses a **reified relation pattern** for provenance:
```
(source)-[:OUT_REL]->(RelationInstance)-[:TO]->(target)
(Evidence)-[:SUPPORTS]->(RelationInstance)
(Evidence)-[:FROM_PASSAGE]->(Passage)
(CanonicalEntity)<-[:INSTANCE_OF_CANONICAL]-(Entity)
```

Full contract: [`docs/graph_contract.md`](docs/graph_contract.md)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ingest` | Upload and ingest a PDF |
| `GET` | `/api/ingest/{job_id}` | Poll ingest job status |
| `GET` | `/api/graph/semantic` | Fetch graph (nodes/edges/meta) |
| `GET` | `/api/graph/node/{id}` | Node detail with evidence and citations |
| `POST` | `/api/query/semantic` | Grounded semantic Q&A |

---

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Neo4j instance (local or [AuraDB free tier](https://neo4j.com/cloud/platform/aura-graph-database/))
- [Groq API key](https://console.groq.com/)
- [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Install

```bash
git clone https://github.com/your-username/mindmap-ai.git
cd mindmap-ai
poetry install
cd frontend && npm install && cd ..
```

### 2. Configure

```bash
cp backend/.env.example .env
```

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
```

### 3. Run

```bash
# Backend
poetry run uvicorn backend.app.main:app --reload

# Frontend (separate terminal)
cd frontend && npm run dev
```

### 4. Seed demo graph (optional)

```bash
poetry run python backend/tools/seed_smoke_graph.py
```

---

## Tests & Quality

```bash
# Backend (161 tests)
poetry run pytest backend/tests

# Frontend unit (58 tests)
cd frontend && npm test

# E2E smoke (6 tests)
cd frontend && npm run test:e2e

# Semantic eval
poetry run python backend/tools/run_semantic_eval.py
```

| Metric | Result |
|--------|--------|
| Backend tests | 161 / 161 passed |
| Frontend tests | 58 / 58 passed |
| E2E tests | 6 / 6 passed |
| Intent accuracy | 100% |
| Hallucination rate | 0% |
| Evidence presence | 74% |
| Insight presence | 89% |

---

## Project Structure

```
backend/
  app/
    api/          # FastAPI routers
    core/         # DB connection, config
    domain/       # Identity and ID generation
    schemas/      # Pydantic request/response models
    services/
      extraction/ # LLM extraction pipeline
      graph/      # Neo4j writers
      ingestion/  # Ingest job orchestration
      normalization/
      parsing/    # PDF parsing, passage splitting
      query/      # Semantic query pipeline
  evals/          # Deterministic eval fixtures
  tests/          # Unit + integration tests
  tools/          # Eval runner, seed scripts

frontend/
  app/
    components/   # SemanticGraphViewer, CommandCenter, Inspector, FileLibrary…
    lib/          # API client, types, constants
    store/        # Zustand global state
  tests/e2e/      # Playwright smoke tests
```

---

## Docs

| Document | Purpose |
|----------|---------|
| [`docs/architecture.md`](docs/architecture.md) | Service layers, pipeline, touch list |
| [`docs/graph_contract.md`](docs/graph_contract.md) | Graph pattern (authoritative) |
| [`docs/ontology_v1.md`](docs/ontology_v1.md) | Entity and relation types |
| [`docs/extraction_contract.md`](docs/extraction_contract.md) | Extraction I/O schema |
| [`docs/status.md`](docs/status.md) | Sprint history and checklist |
