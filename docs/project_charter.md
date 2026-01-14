## 🎯 Goal

To develop a high-performance GraphRAG (Graph Retrieval-Augmented Generation) system capable of ingesting complex academic literature, converting unstructured text into a structured Neo4j Knowledge Graph, and enabling semantic queries through a FastAPI backend.

## 👥 Target Audience

- Primary: Master's Degree Admissions Committee (Demonstration of Advanced System Design & AI Engineering)  
- Secondary: Researchers needing to visualize connections between academic papers  

## ⚙️ Technical Implementation Status

### ✅ Phase 1: Core Engine (Completed)

- Framework: Established FastAPI application structure with Poetry dependency management  
- Ingestion Pipeline: Implemented IngestionService using LangChain Experimental  
- Integrated PyPDFLoader for document parsing  
- Successfully connected to Neo4j via neo4j-driver  
- Retrieval Logic: Developed Neighborhood Search strategy  
- Integrated Llama-3-70b (Groq) for high-speed Cypher generation  

### 🔄 Phase 2: Optimization & Visualization (In Progress)

- Frontend: Developing a Next.js dashboard for graph visualization  
- Dockerization: Creating docker-compose for unified deployment  
- Testing: Adding unit tests for parser edge-cases  

## 📏 Success Metrics

- Accuracy: Extracted graph nodes must strictly follow the schema  
- Performance: Query response time under 3 seconds  
- Stability: API handles PDF parsing errors and background tasks gracefully  