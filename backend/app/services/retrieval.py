import os
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
            allow_dangerous_requests=True
        )
    
    def answer_question(self, query: str):
        logger.info(f"Processing query: {query}")
        try:
            response = self.chain.invoke({"query": query})
            return response
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {"result": f"Error: {str(e)}"}