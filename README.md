# MindMap-AI: Academic GraphRAG Agent 🧠

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain_Experimental-1C3C3C?style=for-the-badge&logo=chainlink&logoColor=white)

## 📖 Abstract (Proje Özeti)

**MindMap-AI**, akademik makaleleri (PDF) analiz ederek derinlemesine bir **Bilgi Grafiği'ne (Knowledge Graph)** dönüştüren ve bu grafik üzerinde bağlamsal sorgulama yapabilen gelişmiş bir RAG (Retrieval-Augmented Generation) sistemidir.

Standart RAG sistemleri metinleri vektör olarak saklarken, MindMap-AI kavramlar arasındaki **ilişkileri (Relationships)** modeller. Bu sayede, *"Transformer mimarisi ile RNN arasındaki temel farklar nelerdir?"* gibi kompleks sorulara, sadece kelime eşleşmesiyle değil, anlamsal bağları takip ederek yanıt verir.

## 🏗 System Architecture (Mimari)

Sistem **Clean Architecture** prensiplerine göre modüler olarak tasarlanmıştır:

### 1. Ingestion Engine (Veri İşleme)

- **PDF Parsing:** `PyPDFLoader` ile sayfa sayfa ham metin çıkarımı (metadata korunur)  
- **Smart Chunking:** `RecursiveCharacterTextSplitter` ile bağlamı koruyan parçalama (chunk_size=1000, overlap=200)  
- **Embedding Generation:** OpenAI `text-embedding-3-small` ile her chunk için vektör oluşturma  
- **Hierarchical Storage:** Neo4j'de `Document` → `Chunk` hiyerarşik yapısı (`BELONGS_TO` ilişkisi)  
- **Batch Processing:** UNWIND ile toplu insert işlemleri (performans optimizasyonu)

### 2. Knowledge Store (Veri Depolama)

- **Neo4j Graph DB:** Yapılandırılmış verinin saklandığı grafik veritabanı

### 3. Retrieval Engine (Bilgi Getirme)

- **Neighborhood Search Strategy:**  
  Klasik vektör araması yerine, sorulan kavramın grafikteki "komşularını" (1-hop relationships) bularak yanıt üretme stratejisi. Bu, kopuk bilgi sorununu çözer.

### 4. API Layer (Sunum Katmanı)

- **FastAPI:** Asenkron `background_tasks` ile PDF işleme ve anlık Chat uç noktaları

## 🛠 Tech Stack

| Component | Technology | Description |
|---------|------------|-------------|
| **LLM (Chat)** | Llama-3.3-70b (Groq) | Yüksek hızlı çıkarım ve JSON modu desteği |
| **Embeddings** | OpenAI text-embedding-3-small | Chunk'lar için vektör oluşturma |
| **Backend Framework** | FastAPI | Asenkron API yönetimi |
| **Orchestration** | LangChain | LLM zincirleri ve Graph transformasyonları |
| **Database** | Neo4j | Graph veritabanı (AuraDB veya Local) |
| **Dependency Mgmt** | Poetry | Paket ve sanal ortam yönetimi |

## 🚀 Installation & Setup

### Prerequisites

- Python 3.10+  
- Neo4j Database (URI, Username, Password)  
- Groq API Key (for LLM/chat)  
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

### Current Migration Status

- semantic ingestion = **primary**
- semantic graph read = **new primary read path**
- legacy chat/vector retrieval = **migration mode**

### 1. Ingest PDF

Endpoint: `POST /api/ingest`  
Mode options:
- `mode=semantic` (default, primary)
- `mode=legacy` (fallback chunk/embedding path)

### 2. Read Graph

- `GET /api/graph` → semantic default response contract (`nodes`, `edges`, `meta`)
- `GET /api/graph/semantic` → semantic graph (same contract)
- `GET /api/graph/legacy` → legacy `Document/Chunk` graph (`nodes`, `links`)

Semantic filters on `GET /api/graph`:
- `document_id`
- `node_types` (supports both `node_types=A,B` and repeated params)
- `include_structural`
- `include_evidence`
- `include_citations`

### 3. Chat

Endpoint: `POST /api/chat`  
Status: current chat path uses **legacy retrieval**. Semantic query chat is pending.

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
- Integration contract tests for `/api/extract` and `/api/graph/semantic`

Run locally:

```bash
poetry run pytest backend/tests
poetry run python -m compileall backend/app
```

Semantic graph endpoint contract checks now include:

- Empty graph response shape (`nodes`, `edges`, `meta`)
- `node_types` query parsing for both CSV and repeated parameter forms

### Manual Ingestion Script

You can also run ingestion manually:

```bash
python run_ingest.py
```

Edit `PDF_PATH` in the script to process different files.
This script is a legacy/debug helper.

### Query Testing

Test queries interactively:

```bash
python run_query.py
```

This script calls the current legacy retrieval path for diagnostics.

---