import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from loguru import logger
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

load_dotenv()

class GraphRAGService:
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

        # 3. V7 PROMPT - "NEIGHBORHOOD SEARCH" (MAHALLE ARAMASI)
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

        # 4. Zinciri Oluştur
        self.chain = GraphCypherQAChain.from_llm(
            graph=self.graph,
            llm=self.llm,
            cypher_prompt=cypher_prompt,
            verbose=True,
            allow_dangerous_requests=True,
            return_intermediate_steps=True
        )
    
    def _extract_node_ids_from_results(self, query_results: Any) -> List[str]:
        """Extract node IDs from Neo4j query results.
        
        Handles different Neo4j result formats robustly:
        - Neo4j v5+: uses element_id
        - Older versions: might use id
        - Dictionary results: might have an 'id' key
        
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
    
    def answer_question(self, query: str, include_node_ids: bool = False) -> Dict[str, Any]:
        """Answer a question using the graph and optionally include related node IDs.
        
        Args:
            query: The user's question.
            include_node_ids: Whether to include related node IDs in the response.
            
        Returns:
            dict: Response with 'result' (answer text) and optionally 'related_node_ids'.
        """
        logger.info(f"Processing query: {query}")
        cypher_query_generated = None
        try:
            # Generate answer using the chain with intermediate_steps enabled
            response = self.chain.invoke({"query": query})
            
            # Extract answer text
            answer_text = response.get("result", response.get("answer", ""))
            
            result = {"result": answer_text}
            
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
                    
                    # Extract node IDs from query_results (these will be node 'id' properties, not element_id)
                    node_name_ids = []
                    if query_results is not None:
                        logger.info(f"Query results type: {type(query_results)}")
                        if isinstance(query_results, dict):
                            logger.info(f"Query results keys: {list(query_results.keys())[:10]}")
                        node_name_ids = self._extract_node_ids_from_results(query_results)
                        logger.info(f"Extracted {len(node_name_ids)} node name IDs from query_results. First 5: {node_name_ids[:5]}")
                    
                    # Convert node name IDs (id property) to element_ids by re-executing Cypher query
                    # This ensures we return element_ids that match the graph endpoint format
                    node_ids = []
                    if cypher_query_generated:
                        logger.info(f"Re-executing Cypher query to get element_ids: {cypher_query_generated[:100]}...")
                        try:
                            from backend.app.core.db import Neo4jDatabase
                            db = Neo4jDatabase()
                            if not db.driver:
                                db.connect()
                            
                            records, summary, keys = db.driver.execute_query(
                                cypher_query_generated,
                                database_="neo4j"
                            )
                            
                            # Extract element_ids from records (same format as graph endpoint)
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
                            # Fallback: if re-execution fails, use node name IDs and hope frontend can match by name
                            logger.warning(f"Falling back to node name IDs: {node_name_ids[:5]}")
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
            error_result = {"result": f"Error: {str(e)}"}
            if include_node_ids:
                error_result["related_node_ids"] = []
            return error_result