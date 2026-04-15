# MindMap-AI: Semantic Knowledge Graph-based Research Copilot

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain_Experimental-1C3C3C?style=for-the-badge&logo=chainlink&logoColor=white)

## Product Focus

MindMap-AI converts academic PDFs into a semantic knowledge graph and answers questions directly from graph provenance.
The primary runtime path is semantic ingestion and semantic query.

Primary pipeline:

- PDF parse
- extraction and normalization
- graph write to Neo4j
- graph read through semantic API contracts
- semantic grounded query (`/api/query/semantic`)

## Primary Runtime

- semantic ingestion (`POST /api/ingest`, default mode)
- semantic graph read (`GET /api/graph`)
- semantic grounded query (`POST /api/query/semantic`)

## System Architecture

The current architecture follows a semantic graph-first model:

1. Ingestion: parse documents and extract typed entities, relations, evidence, and citations.
2. Graph write: persist semantic structures and provenance chains to Neo4j.
3. Graph read: expose semantic graph contracts for frontend and filtering.
4. Semantic query: deterministic, evidence-backed answers from graph traversals.

Legacy code is quarantined and excluded from active runtime paths.

## 🛠 Tech Stack

| Component | Technology | Description |
|---------|------------|-------------|
| **LLM (Copilot)** | Llama-3.3-70b (Groq) | Yüksek hızlı çıkarım ve JSON modu desteği |
| **Embeddings** | OpenAI text-embedding-3-small | Chunk'lar için vektör oluşturma |
| **Backend Framework** | FastAPI | Asenkron API yönetimi |
| **Orchestration** | LangChain | LLM zincirleri ve Graph transformasyonları |
| **Database** | Neo4j | Graph veritabanı (AuraDB veya Local) |
| **Dependency Mgmt** | Poetry | Paket ve sanal ortam yönetimi |

## 🚀 Installation & Setup

### Prerequisites

- Python 3.10+  
- Neo4j Database (URI, Username, Password)  
- Groq API Key (for LLM/copilot)  
- OpenAI API Key (for embeddings)  

### 1. Clone & Install

```bash
git clone https://github.com/your-username/mindmap-ai.git
cd mindmap-ai
poetry install
poetry shell
```

### 2. Environment Configuration

Copy the example environment file and fill in your values:

```bash
cp env.example .env
```

Edit `.env` file with your actual credentials:

```env
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password

# API Keys
GROQ_API_KEY=gsk_your_groq_api_key
OPENAI_API_KEY=sk-your_openai_api_key
```

**Get your API keys:**
- Groq API Key: https://console.groq.com/
- OpenAI API Key: https://platform.openai.com/api-keys

### 3. Run the API

uvicorn backend.app.main:app --reload

## ⚡ API Usage

### Current Runtime Status

- semantic ingestion = **primary**
- semantic graph read = **primary**
- semantic grounded query = **primary**

### Frontend Status

- Frontend graph viewer now uses semantic `GET /api/graph` response contract (`nodes`, `edges`, `meta`).
- Graph exploration includes preset modes: **Semantic**, **Evidence**, **Citation**.
- Document-focused filtering is wired into graph fetch filters (`document_id`, include toggles).
- Query panel uses a single **Semantic Query** mode.
- Semantic Query renders evidence-first answers and supports inspector page jump from evidence cards.

### 1. Ingest PDF

Endpoint: `POST /api/ingest`  
Mode options:
- `mode=semantic` (default, primary)

### 2. Read Graph

- `GET /api/graph` → semantic default response contract (`nodes`, `edges`, `meta`)
- `GET /api/graph/semantic` → semantic graph (same contract)

Semantic filters on `GET /api/graph`:
- `document_id`
- `node_types` (supports both `node_types=A,B` and repeated params)
- `include_structural`
- `include_evidence`
- `include_citations`

### 3. Grounded Semantic Query

Endpoint: `POST /api/query/semantic`  
Status: **primary query/QA path** (graph-backed, evidence-backed, deterministic template answer in Sprint 10).

Request contract:
- `question` (required)
- `document_id` (optional)
- `node_types` (optional)
- `max_evidence` (optional, default 5)
- `include_citations` (optional, default true)

Response contract:
- `answer`
- `evidence[]` (`relation_type`, `page`, `snippet`, `related_node_ids`, document + citation fields)
- `related_nodes[]`
- `citations[]`
- `confidence`
- `mode = "semantic_grounded"`

### 4. Research Copilot Query

Use `POST /api/query/semantic` for query/copilot interactions.

## 📊 Active Graph Docs

Use these as source of truth for the semantic model:
- `docs/ontology_v1.md`
- `docs/extraction_contract.md`
- `docs/graph_storage_model.md`

Deprecated/historical schema docs remain under `docs/deprecated/`.

---

## 🛠 Development

### Testing and Quality Gates

Backend regression checks introduced in Sprint 8:

- Unit tests for identity and normalization logic
- Unit tests for section/reference/inline-citation/document parsing
- Unit tests for semantic graph response shaping
- Integration contract tests for `/api/extract`, `/api/graph/semantic`, and `/api/query/semantic`

Run locally:

```bash
poetry run pytest backend/tests
poetry run python -m compileall backend/app
```

Semantic graph endpoint contract checks now include:

- Empty graph response shape (`nodes`, `edges`, `meta`)
- `node_types` query parsing for both CSV and repeated parameter forms

Semantic query endpoint contract checks include:

- Response mode and evidence-backed shape (`answer`, `evidence`, `related_nodes`, `citations`, `confidence`)
- Request validation for required/bounded semantic query fields

### Manual Ingestion Script

You can also run ingestion manually:

```bash
python tools/legacy/run_ingest.py
```

Edit `PDF_PATH` in the script to process different files.
This script is a legacy/debug helper.

### Query Testing

Test queries interactively:

```bash
python tools/legacy/run_query.py
```

This script calls the current legacy retrieval path for diagnostics.

---