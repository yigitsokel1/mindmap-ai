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

- **PDF Parsing:** `PyPDFLoader` ile ham metin çıkarımı  
- **Smart Chunking:** `RecursiveCharacterTextSplitter` ile bağlamı koruyan parçalama  
- **Graph Extraction:** `LangChain Experimental (LLMGraphTransformer)` ve **Llama-3-70b** kullanılarak Node (Varlık) ve Relationship (İlişki) çıkarımı  
- **Strict Schema:** Halüsinasyonu önlemek için katı şema zorlaması (`Paper`, `Author`, `Concept`, `Institution`)

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
| **LLM** | Llama-3.3-70b (Groq) | Yüksek hızlı çıkarım ve JSON modu desteği |
| **Backend Framework** | FastAPI | Asenkron API yönetimi |
| **Orchestration** | LangChain | LLM zincirleri ve Graph transformasyonları |
| **Database** | Neo4j | Graph veritabanı (AuraDB veya Local) |
| **Dependency Mgmt** | Poetry | Paket ve sanal ortam yönetimi |

## 🚀 Installation & Setup

### Prerequisites

- Python 3.10+  
- Neo4j Database (URI, Username, Password)  
- Groq API Key  

### 1. Clone & Install

```bash
git clone https://github.com/your-username/mindmap-ai.git
cd mindmap-ai
poetry install
poetry shell
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=gsk_...
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

## 2. Environment Configuration

Create a `.env` file in the root directory:

GROQ_API_KEY=gsk_...  
NEO4J_URI=bolt://localhost:7687  
NEO4J_USERNAME=neo4j  
NEO4J_PASSWORD=your_password  

## 3. Run the API

uvicorn backend.app.main:app --reload

## ⚡ API Usage

### 1. Ingest PDF (Process Document)

Endpoint: POST /api/ingest  
Body: { "file_path": "data/attention-is-all-you-need.pdf" }  
Process: Parses PDF → Extracts Entities → Writes to Neo4j (Background Task)

### 2. Chat with Graph

Endpoint: POST /api/chat  
Body: { "query": "How does the Attention mechanism differ from Recurrent layers?" }  
Process: Converts Question to Cypher → Retrieves Neighborhood → Generates Answer

## 📊 Graph Schema (Ontology)

The system enforces the following structure defined in docs/graph_schema.md:

### Nodes

- Paper: The research document  
- Author: Researchers  
- Concept: Technical terms (e.g., "Self-Attention")  
- Institution: Affiliations  

### Relationships

- (:Author)-[:AUTHORED]->(:Paper)  
- (:Paper)-[:MENTIONS]->(:Concept)  
- (:Author)-[:AFFILIATED_WITH]->(:Institution)  

---