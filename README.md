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

### 1. Ingest PDF (Process Document)

Endpoint: POST /api/ingest  
Body: 
```json
{
  "file_path": "data/attention-is-all-you-need-paper.pdf",
  "file_name": "attention-is-all-you-need-paper.pdf"  // optional
}
```

Process: 
- Parses PDF page-by-page (preserves page metadata)
- Splits into chunks (1000 chars, 200 overlap)
- Generates embeddings for each chunk
- Creates Document and Chunk nodes in Neo4j
- Links chunks to document via BELONGS_TO relationship
- Returns: `{ "doc_id": "...", "chunk_count": 123, "status": "success" }`

**Note:** Processing runs as a background task. Check logs for progress.

### 2. Chat with Graph

Endpoint: POST /api/chat  
Body: { "query": "How does the Attention mechanism differ from Recurrent layers?" }  
Process: Converts Question to Cypher → Retrieves Neighborhood → Generates Answer

## 📊 Graph Schema (Ontology)

### Ingestion Schema (Document Storage)

The ingestion system creates a hierarchical structure:

**Nodes:**
- `Document`: Represents a PDF file
  - Properties: `id` (UUID), `name`, `created_at` (timestamp)
- `Chunk`: Represents a text chunk from the document
  - Properties: `id` (UUID), `text`, `page` (int), `source`, `embedding` (List[Float])

**Relationships:**
- `(:Chunk)-[:BELONGS_TO]->(:Document)`

### Query Schema (Knowledge Graph)

For advanced querying, the system can extract knowledge graphs with the following structure (defined in `docs/graph_schema.md`):

**Nodes:**
- `Paper`: The research document  
- `Author`: Researchers  
- `Concept`: Technical terms (e.g., "Self-Attention")  
- `Institution`: Affiliations  

**Relationships:**
- `(:Author)-[:AUTHORED]->(:Paper)`  
- `(:Paper)-[:MENTIONS]->(:Concept)`  
- `(:Author)-[:AFFILIATED_WITH]->(:Institution)`  

---

## 🛠 Development

### Manual Ingestion Script

You can also run ingestion manually:

```bash
python run_ingest.py
```

Edit `PDF_PATH` in the script to process different files.

### Query Testing

Test queries interactively:

```bash
python run_query.py
```

---