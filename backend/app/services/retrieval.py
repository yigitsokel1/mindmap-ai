"""GraphRAG retrieval service with vector search and document filtering.

This module provides GraphRAGService for querying the knowledge graph
using vector similarity search with optional document filtering.
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from loguru import logger

# Try to import OpenAI embeddings
try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import OpenAIEmbeddings
    except ImportError:
        raise ImportError(
            "OpenAIEmbeddings not found. Please install langchain-openai: "
            "pip install langchain-openai"
        )

from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

from backend.app.core.db import Neo4jDatabase

load_dotenv()


class GraphRAGService:
    """Service for querying knowledge graphs with vector search and document filtering.
    
    Supports both graph-based queries and vector similarity search with optional
    document filtering for focused retrieval.
    """
    
    def __init__(self):
        # 1. Veritabanı Bağlantısı
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )

        # Şemayı tazele
        self.graph.refresh_schema()
        
        # 2. LLM (70B Model)
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        
        self.llm = ChatGroq(
            temperature=0,
            model="llama-3.3-70b-versatile",
            groq_api_key=groq_api_key
        )
        
        # 3. OpenAI Embeddings for vector search
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=openai_api_key,
            model="text-embedding-3-small"
        )

        # 4. V7 PROMPT - "NEIGHBORHOOD SEARCH" (MAHALLE ARAMASI)
        # Yol bulamazsan bile, kavramların kendisini ve komşularını getir diyoruz.
        CYPHER_GENERATION_TEMPLATE = """Task: Generate Cypher statement to query a graph database.
        
        Instructions:
        1. Use only the provided relationship types and properties in the schema.
        2. Do not use inline property matching syntax.
        3. ALWAYS use `toLower(n.id) CONTAINS "value"` for matching.
        4. STRATEGY: 
           - Instead of forcing `shortestPath` (which fails if disconnected), retrieve the "Neighborhood" of relevant nodes.
           - Find nodes related to the first term OR the second term.
           - Return the nodes and their immediate relationships.
        
        Schema:
        {schema}
        
        The question is:
        {question}

        Example of correct logic (Neighborhood Strategy):
        Question: "How are Attention mechanisms related to Recurrent models?"
        Cypher: MATCH (n:Concept) WHERE toLower(n.id) CONTAINS "attention" OR toLower(n.id) CONTAINS "recurrent" OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50
        
        Note: Do not include any explanations. Just the Cypher query.
        
        Cypher Query:"""

        cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=CYPHER_GENERATION_TEMPLATE
        )

        # 5. Zinciri Oluştur
        self.chain = GraphCypherQAChain.from_llm(
            graph=self.graph,
            llm=self.llm,
            cypher_prompt=cypher_prompt,
            verbose=True,
            allow_dangerous_requests=True,
            return_intermediate_steps=True
        )
        
        # 6. Neo4j Database connection for direct queries
        self.db = Neo4jDatabase()
        if not self.db.driver:
            self.db.connect()
    
    def _vector_search_chunks(
        self, 
        query_embedding: List[float], 
        top_k: int = 5,
        doc_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search on Chunk nodes.
        
        Uses cosine similarity to find the most relevant chunks.
        Optionally filters by document ID.
        
        Args:
            query_embedding: The query embedding vector.
            top_k: Number of top results to return.
            doc_id: Optional document ID to filter chunks.
            
        Returns:
            List of dictionaries with chunk text, page, document name, and similarity score.
        """
        try:
            # Build Cypher query with optional document filtering
            if doc_id:
                # Filter by specific document
                query = """
                MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document {id: $doc_id})
                WITH c, d,
                    gds.similarity.cosine(c.embedding, $query_embedding) AS score
                WHERE score > 0.0
                RETURN c, d, c.text AS text, c.page AS page, d.name AS doc_name, score
                ORDER BY score DESC
                LIMIT $top_k
                """
                params = {
                    "query_embedding": query_embedding,
                    "doc_id": doc_id,
                    "top_k": top_k
                }
            else:
                # Search all chunks (global search)
                query = """
                MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
                WITH c, d,
                    gds.similarity.cosine(c.embedding, $query_embedding) AS score
                WHERE score > 0.0
                RETURN c, d, c.text AS text, c.page AS page, d.name AS doc_name, score
                ORDER BY score DESC
                LIMIT $top_k
                """
                params = {
                    "query_embedding": query_embedding,
                    "top_k": top_k
                }
            
            # Execute query
            records, _, _ = self.db.driver.execute_query(
                query,
                params,
                database_="neo4j"
            )
            
            # Format results
            results = []
            for record in records:
                c_node = record.get("c")
                d_node = record.get("d")
                
                # Extract node IDs (element_id for Neo4j 5.x, id for older versions)
                chunk_id = None
                doc_id_val = None
                
                if c_node:
                    try:
                        chunk_id = str(c_node.element_id)
                    except AttributeError:
                        chunk_id = str(c_node.id)
                
                if d_node:
                    try:
                        doc_id_val = str(d_node.element_id)
                    except AttributeError:
                        doc_id_val = str(d_node.id)
                
                results.append({
                    "text": record.get("text", ""),
                    "page": record.get("page", 0),
                    "doc_name": record.get("doc_name", "Unknown"),
                    "score": record.get("score", 0.0),
                    "chunk_id": chunk_id,
                    "doc_id": doc_id_val
                })
            
            logger.info(f"Vector search returned {len(results)} chunks (doc_id={doc_id})")
            return results
            
        except Exception as e:
            # Fallback: If GDS similarity function is not available, use manual cosine
            logger.warning(f"GDS similarity not available, using manual cosine: {e}")
            return self._vector_search_chunks_manual(query_embedding, top_k, doc_id)
    
    def _vector_search_chunks_manual(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        doc_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Manual vector search using Python cosine similarity.
        
        Fallback method when GDS functions are not available.
        
        Args:
            query_embedding: The query embedding vector.
            top_k: Number of top results to return.
            doc_id: Optional document ID to filter chunks.
            
        Returns:
            List of dictionaries with chunk text, page, document name, and similarity score.
        """
        import math
        
        try:
            # Fetch all chunks (or filtered by doc_id)
            if doc_id:
                query = """
                MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document {id: $doc_id})
                RETURN c, d, c.text AS text, c.page AS page, c.embedding AS embedding, d.name AS doc_name
                """
                params = {"doc_id": doc_id}
            else:
                query = """
                MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document)
                RETURN c, d, c.text AS text, c.page AS page, c.embedding AS embedding, d.name AS doc_name
                """
                params = {}
            
            records, _, _ = self.db.driver.execute_query(
                query,
                params,
                database_="neo4j"
            )
            
            # Calculate cosine similarity for each chunk
            scored_chunks = []
            for record in records:
                chunk_embedding = record.get("embedding", [])
                if not chunk_embedding:
                    continue
                
                c_node = record.get("c")
                d_node = record.get("d")
                
                # Extract node IDs (element_id for Neo4j 5.x, id for older versions)
                chunk_id = None
                doc_id_val = None
                
                if c_node:
                    try:
                        chunk_id = str(c_node.element_id)
                    except AttributeError:
                        chunk_id = str(c_node.id)
                
                if d_node:
                    try:
                        doc_id_val = str(d_node.element_id)
                    except AttributeError:
                        doc_id_val = str(d_node.id)
                
                # Cosine similarity
                dot_product = sum(a * b for a, b in zip(query_embedding, chunk_embedding))
                magnitude_a = math.sqrt(sum(a * a for a in query_embedding))
                magnitude_b = math.sqrt(sum(b * b for b in chunk_embedding))
                
                if magnitude_a == 0 or magnitude_b == 0:
                    score = 0.0
                else:
                    score = dot_product / (magnitude_a * magnitude_b)
                
                scored_chunks.append({
                    "text": record.get("text", ""),
                    "page": record.get("page", 0),
                    "doc_name": record.get("doc_name", "Unknown"),
                    "score": score,
                    "chunk_id": chunk_id,
                    "doc_id": doc_id_val
                })
            
            # Sort by score and return top_k
            scored_chunks.sort(key=lambda x: x["score"], reverse=True)
            results = scored_chunks[:top_k]
            
            logger.info(f"Manual vector search returned {len(results)} chunks (doc_id={doc_id})")
            return results
            
        except Exception as e:
            logger.error(f"Error in manual vector search: {e}")
            return []
    
    def _build_context_with_citations(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string with page citations for LLM.
        
        Args:
            chunks: List of chunk dictionaries with text, page, doc_name.
            
        Returns:
            Formatted context string with citations.
        """
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            page = chunk.get("page", 0)
            doc_name = chunk.get("doc_name", "Unknown")
            score = chunk.get("score", 0.0)
            
            # Format: [Citation: Document Name, Page X]
            citation = f"[Source: {doc_name}, Page {page}]"
            context_parts.append(f"{citation}\n{text}")
        
        return "\n\n---\n\n".join(context_parts)
    
    def answer_question(
        self, 
        query: str, 
        include_node_ids: bool = False,
        doc_id: Optional[str] = None,
        use_vector_search: bool = True,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Answer a question using vector search or graph query.
        
        Args:
            query: The user's question.
            include_node_ids: Whether to include related node IDs in the response.
            doc_id: Optional document ID to filter search to specific document.
            use_vector_search: Whether to use vector search (True) or graph query (False).
            top_k: Number of top chunks to retrieve for vector search.
            
        Returns:
            dict: Response with 'result' (answer text), optionally 'related_node_ids',
                  and 'sources' (list of citations).
        """
        logger.info(f"Processing query: {query} (doc_id={doc_id}, vector_search={use_vector_search})")
        
        try:
            if use_vector_search:
                # Vector-based RAG approach
                # 1. Generate query embedding
                query_embedding = self.embeddings.embed_query(query)
                logger.info("Generated query embedding")
                
                # 2. Perform vector search
                chunks = self._vector_search_chunks(query_embedding, top_k=top_k, doc_id=doc_id)
                
                if not chunks:
                    return {
                        "result": "I couldn't find any relevant information to answer your question.",
                        "sources": []
                    }
                
                # 3. Build context with citations
                context = self._build_context_with_citations(chunks)
                
                # 4. Create prompt with context
                prompt = f"""You are a helpful assistant that answers questions based on the provided context from academic documents.

Context from documents:
{context}

Question: {query}

Instructions:
- Answer the question based ONLY on the provided context.
- If the context doesn't contain enough information, say so.
- Include page citations when referencing specific information (e.g., "According to page 5...").
- Be concise and accurate.

Answer:"""
                
                # 5. Generate answer using LLM
                response = self.llm.invoke(prompt)
                answer_text = response.content if hasattr(response, 'content') else str(response)
                
                # 6. Extract sources for citations
                sources = [
                    {
                        "doc_name": chunk.get("doc_name", "Unknown"),
                        "page": chunk.get("page", 0),
                        "score": chunk.get("score", 0.0)
                    }
                    for chunk in chunks
                ]
                
                result = {
                    "result": answer_text,
                    "sources": sources
                }
                
                # Extract node IDs if requested (from chunks)
                if include_node_ids:
                    # Collect unique Document node IDs from chunks (prefer Document nodes for navigation)
                    # Document nodes are more stable and visible in the graph
                    # CRITICAL: Preserve order by using list instead of set, prioritizing first chunks
                    # This ensures the most relevant Document (first in chunks) is focused first
                    node_ids_list = []
                    seen_doc_ids = set()
                    for chunk in chunks:
                        # Add Document node ID (prefer Document nodes for navigation)
                        if "doc_id" in chunk and chunk["doc_id"]:
                            doc_id = chunk["doc_id"]
                            # Only add if not seen yet - preserves order from chunks
                            if doc_id not in seen_doc_ids:
                                node_ids_list.append(doc_id)
                                seen_doc_ids.add(doc_id)
                    
                    result["related_node_ids"] = node_ids_list
                    logger.info(f"Vector search extracted {len(node_ids_list)} Document node IDs (ordered) from {len(chunks)} chunks. First: {node_ids_list[0] if node_ids_list else 'None'}")
                else:
                    result["related_node_ids"] = []
                
                return result
                
            else:
                # Original graph-based approach
                return self._answer_question_graph(query, include_node_ids)
                
        except Exception as e:
            logger.error(f"Error answering question: {e}", exc_info=True)
            error_result = {"result": f"Error: {str(e)}", "sources": []}
            if include_node_ids:
                error_result["related_node_ids"] = []
            return error_result
    
    def _answer_question_graph(
        self, 
        query: str, 
        include_node_ids: bool = False
    ) -> Dict[str, Any]:
        """Answer question using graph-based approach (original method).
        
        Args:
            query: The user's question.
            include_node_ids: Whether to include related node IDs.
            
        Returns:
            dict: Response with 'result' and optionally 'related_node_ids'.
        """
        cypher_query_generated = None
        try:
            # Generate answer using the chain with intermediate_steps enabled
            response = self.chain.invoke({"query": query})
            
            # Extract answer text
            answer_text = response.get("result", response.get("answer", ""))
            
            result = {"result": answer_text, "sources": []}
            
            # Extract node IDs from intermediate_steps if requested
            if include_node_ids:
                try:
                    # Get intermediate_steps from response
                    intermediate_steps = response.get("intermediate_steps", [])
                    logger.info(f"Intermediate steps structure: {type(intermediate_steps)}")
                    if isinstance(intermediate_steps, list):
                        logger.info(f"Intermediate steps length: {len(intermediate_steps)}")
                        for i, step in enumerate(intermediate_steps):
                            logger.info(f"Step {i} type: {type(step)}, preview: {str(step)[:100]}")
                    
                    # GraphCypherQAChain intermediate_steps format:
                    # [(cypher_query_string, query_results_dict), ...]
                    # OR: [cypher_query_string, query_results_dict]
                    query_results = None
                    
                    if isinstance(intermediate_steps, list) and len(intermediate_steps) >= 1:
                        # Check if it's a list of tuples (first format)
                        if isinstance(intermediate_steps[0], tuple) and len(intermediate_steps[0]) >= 2:
                            # First format: [(query, results), ...]
                            cypher_query_generated = intermediate_steps[0][0]
                            query_results = intermediate_steps[0][1]
                        elif len(intermediate_steps) >= 2:
                            # Second format: [query_dict, results_dict]
                            # Extract query from dict
                            if isinstance(intermediate_steps[0], dict) and "query" in intermediate_steps[0]:
                                cypher_query_generated = intermediate_steps[0]["query"]
                            elif isinstance(intermediate_steps[0], str):
                                cypher_query_generated = intermediate_steps[0]
                            query_results = intermediate_steps[1]
                        elif isinstance(intermediate_steps[0], dict):
                            # Might be results dict directly, check if it has query
                            if "query" in intermediate_steps[0]:
                                cypher_query_generated = intermediate_steps[0]["query"]
                            query_results = intermediate_steps[0]
                    
                    # Extract node IDs from query_results
                    node_name_ids = []
                    if query_results is not None:
                        logger.info(f"Query results type: {type(query_results)}")
                        if isinstance(query_results, dict):
                            logger.info(f"Query results keys: {list(query_results.keys())[:10]}")
                        node_name_ids = self._extract_node_ids_from_results(query_results)
                        logger.info(f"Extracted {len(node_name_ids)} node name IDs from query_results. First 5: {node_name_ids[:5]}")
                    
                    # Convert node name IDs (id property) to element_ids by re-executing Cypher query
                    node_ids = []
                    if cypher_query_generated:
                        logger.info(f"Re-executing Cypher query to get element_ids: {cypher_query_generated[:100]}...")
                        try:
                            if not self.db.driver:
                                self.db.connect()
                            
                            records, summary, keys = self.db.driver.execute_query(
                                cypher_query_generated,
                                database_="neo4j"
                            )
                            
                            # Extract element_ids from records
                            node_id_set = set()
                            for record in records:
                                for key, value in record.items():
                                    if hasattr(value, 'element_id'):
                                        node_id_set.add(str(value.element_id))
                                    elif hasattr(value, 'start_node'):
                                        node_id_set.add(str(value.start_node.element_id))
                                        node_id_set.add(str(value.end_node.element_id))
                            
                            node_ids = list(node_id_set)
                            logger.info(f"Re-executed query extracted {len(node_ids)} element_ids. First 5: {node_ids[:5]}")
                        except Exception as e:
                            logger.warning(f"Failed to re-execute Cypher query: {e}")
                            node_ids = node_name_ids
                    
                    if node_ids:
                        result["related_node_ids"] = node_ids
                    else:
                        logger.warning(f"Could not extract node IDs. Full response keys: {list(response.keys())}")
                        result["related_node_ids"] = []
                        
                except Exception as e:
                    logger.warning(f"Failed to extract node IDs from intermediate steps: {e}", exc_info=True)
                    result["related_node_ids"] = []
            
            return result
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            error_result = {"result": f"Error: {str(e)}", "sources": []}
            if include_node_ids:
                error_result["related_node_ids"] = []
            return error_result
    
    def _extract_node_ids_from_results(self, query_results: Any) -> List[str]:
        """Extract node IDs from Neo4j query results.
        
        Handles different Neo4j result formats robustly.
        
        Args:
            query_results: The raw database query results from intermediate_steps.
            
        Returns:
            List[str]: List of unique node IDs as strings.
        """
        node_ids = set()
        
        try:
            # Handle list of records (most common format)
            if isinstance(query_results, list):
                for record in query_results:
                    # Handle dictionary records (key-value pairs from RETURN clause)
                    if isinstance(record, dict):
                        for key, value in record.items():
                            node_ids.update(self._extract_node_id_from_value(value))
                    # Handle tuple/list records
                    elif isinstance(record, (tuple, list)):
                        for value in record:
                            node_ids.update(self._extract_node_id_from_value(value))
                    # Handle direct node objects
                    else:
                        node_ids.update(self._extract_node_id_from_value(record))
            
            # Handle single value
            else:
                node_ids.update(self._extract_node_id_from_value(query_results))
            
            unique_ids = list(node_ids)
            logger.info(f"Extracted {len(unique_ids)} unique node IDs from query results")
            return unique_ids
            
        except Exception as e:
            logger.error(f"Error extracting node IDs from results: {e}")
            return []
    
    def _extract_node_id_from_value(self, value: Any) -> set:
        """Extract node ID(s) from a single value.
        
        Args:
            value: A value that might be a node, relationship, or contain nodes.
            
        Returns:
            set: Set of node IDs found in this value.
        """
        node_ids = set()
        
        try:
            # Handle Node objects (Neo4j v5+ uses element_id)
            if hasattr(value, 'element_id'):
                node_ids.add(str(value.element_id))
            # Handle Node objects (older Neo4j versions might use id)
            elif hasattr(value, 'id') and not isinstance(value, dict):
                node_ids.add(str(value.id))
            
            # Handle Relationship objects (extract start and end nodes)
            elif hasattr(value, 'start_node') and hasattr(value, 'end_node'):
                if hasattr(value.start_node, 'element_id'):
                    node_ids.add(str(value.start_node.element_id))
                elif hasattr(value.start_node, 'id'):
                    node_ids.add(str(value.start_node.id))
                
                if hasattr(value.end_node, 'element_id'):
                    node_ids.add(str(value.end_node.element_id))
                elif hasattr(value.end_node, 'id'):
                    node_ids.add(str(value.end_node.id))
            
            # Handle dictionaries (might contain node data)
            elif isinstance(value, dict):
                # Check for 'id' or 'element_id' keys
                if 'element_id' in value:
                    node_ids.add(str(value['element_id']))
                elif 'id' in value:
                    node_ids.add(str(value['id']))
                # Recursively check nested dictionaries
                for nested_value in value.values():
                    node_ids.update(self._extract_node_id_from_value(nested_value))
            
            # Handle lists (e.g., from COLLECT or path expressions)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    node_ids.update(self._extract_node_id_from_value(item))
        
        except Exception as e:
            logger.debug(f"Error extracting node ID from value: {e}")
        
        return node_ids
