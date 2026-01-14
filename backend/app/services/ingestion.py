"""PDF ingestion service for extracting knowledge graphs.

This module provides IngestionService class for processing PDF documents,
extracting structured knowledge graphs using LLM, and storing them in Neo4j.
"""

import logging
import os
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.graphs import Neo4jGraph
from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.core.db import Neo4jDatabase

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting PDF documents and extracting knowledge graphs.
    
    This service handles PDF parsing, text chunking, graph extraction using
    LLM, and storage to Neo4j database following the schema defined in
    docs/graph_schema.md.
    """
    
    def __init__(self) -> None:
        """Initialize the IngestionService.
        
        Sets up ChatGroq LLM, LLMGraphTransformer, Neo4jGraph wrapper, and text splitter.
        Uses environment variables for API keys and database configuration.
        Schema is strictly enforced based on docs/graph_schema.md.
        
        Raises:
            ValueError: If required environment variables are missing.
            RuntimeError: If Neo4j driver is not connected.
        """
        # Initialize Groq LLM
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=groq_api_key,
            temperature=0
        )
        
        # Initialize Neo4j database connection
        self.db = Neo4jDatabase()
        self.db.connect()
        
        if not self.db.driver:
            raise RuntimeError("Neo4j driver is not connected")
        
        # Initialize Neo4jGraph wrapper for LangChain
        # Neo4jGraph uses URI, username, password (not driver)
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_username = os.getenv("NEO4J_USERNAME")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        
        if not neo4j_uri or not neo4j_username or not neo4j_password:
            raise ValueError("Neo4j environment variables are required")
        
        self.graph = Neo4jGraph(
            url=neo4j_uri,
            username=neo4j_username,
            password=neo4j_password
        )
        
        # Define allowed nodes and relationships from graph_schema.md
        allowed_nodes = ["Paper", "Author", "Institution", "Concept"]
        allowed_relationships = ["AUTHORED", "AFFILIATED_WITH", "MENTIONS", "CITES"]
        
        # Initialize LLMGraphTransformer with schema enforcement
        self.llm_transformer = LLMGraphTransformer(
            llm=self.llm,
            allowed_nodes=allowed_nodes,
            allowed_relationships=allowed_relationships,
            strict_mode=True
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        logger.info("IngestionService initialized successfully")
    
    def process_pdf(self, file_path: str) -> dict:
        """Process a PDF file and extract knowledge graph.
        
        Loads PDF, splits into chunks, extracts graph using LLMGraphTransformer,
        and stores in Neo4j.
        
        Args:
            file_path: Path to the PDF file to process.
            
        Returns:
            dict: Summary of processing results with node and relationship counts.
            
        Raises:
            FileNotFoundError: If the PDF file does not exist.
            Exception: If processing or storage fails.
        """
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Processing PDF: {file_path}")
        
        try:
            # Step 1: Load PDF
            loader = PyPDFLoader(str(pdf_path))
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} pages from PDF")
            
            # Step 2: Split into chunks
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"Split into {len(chunks)} chunks")
            
            # Step 3: Convert chunks to Graph Documents using LLMGraphTransformer
            graph_documents = []
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"Processing chunk {i}/{len(chunks)}")
                chunk_docs = self.llm_transformer.convert_to_graph_documents([chunk])
                graph_documents.extend(chunk_docs)
                # Rate limiting: sleep between chunks to avoid 429 errors
                # Groq API has rate limits, so we wait 4 seconds between requests
                if i < len(chunks):
                    time.sleep(4)  # 4 seconds between chunks to reduce rate limit errors
            logger.info(f"Extracted {len(graph_documents)} graph documents")
            
            # Step 4: Store in Neo4j
            if graph_documents:
                self.graph.add_graph_documents(graph_documents)
                
                # Count nodes and relationships created
                total_nodes = sum(len(doc.nodes) for doc in graph_documents)
                total_relationships = sum(len(doc.relationships) for doc in graph_documents)
                
                logger.info(
                    f"Stored {len(graph_documents)} graph documents to Neo4j. "
                    f"Total nodes: {total_nodes}, Total relationships: {total_relationships}"
                )
            else:
                logger.warning("No graph documents extracted from PDF")
            
            # Get final counts from database
            result = self._count_graph_elements()
            
            logger.info(
                f"Processing complete. Total nodes in database: {result['nodes']}, "
                f"Total relationships: {result['relationships']}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise
    
    def _count_graph_elements(self) -> dict:
        """Count nodes and relationships in the Neo4j graph.
        
        Returns:
            dict: Dictionary with 'nodes' and 'relationships' counts.
        """
        try:
            # Count nodes
            node_result, _, _ = self.db.driver.execute_query(
                "MATCH (n) RETURN count(n) as count",
                database_="neo4j"
            )
            node_count = node_result[0]["count"] if node_result else 0
            
            # Count relationships
            rel_result, _, _ = self.db.driver.execute_query(
                "MATCH ()-[r]->() RETURN count(r) as count",
                database_="neo4j"
            )
            rel_count = rel_result[0]["count"] if rel_result else 0
            
            return {
                "nodes": node_count,
                "relationships": rel_count
            }
        except Exception as e:
            logger.error(f"Error counting graph elements: {str(e)}")
            return {"nodes": 0, "relationships": 0}
    
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.db:
            self.db.close()
        logger.info("IngestionService closed")
