"""PDF ingestion service with Multi-PDF & Metadata Support.

This module provides functionality for processing PDF documents,
extracting text chunks with metadata, generating embeddings, and
storing them in Neo4j as a hierarchical structure (Document -> Chunks).
"""

import hashlib
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Try to import OpenAI embeddings from langchain_openai first, fallback to langchain_community
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

from backend.app.core.db import Neo4jDatabase

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting PDF documents with metadata support.
    
    This service handles PDF parsing, text chunking with page metadata,
    embedding generation, and storage to Neo4j database in a hierarchical
    structure: Document -> Chunks (with BELONGS_TO relationships).
    """
    
    def __init__(self) -> None:
        """Initialize the IngestionService.
        
        Sets up OpenAI embeddings, Neo4j database connection, and text splitter.
        Uses environment variables for API keys and database configuration.
        
        Raises:
            ValueError: If required environment variables are missing.
            RuntimeError: If Neo4j driver is not connected.
        """
        # Initialize OpenAI embeddings
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=openai_api_key,
            model="text-embedding-3-small"
        )
        
        # Initialize Neo4j database connection
        self.db = Neo4jDatabase()
        self.db.connect()
        
        if not self.db.driver:
            raise RuntimeError("Neo4j driver is not connected")
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        # Set up uploaded_docs directory
        self.uploaded_docs_dir = Path(__file__).parent.parent.parent.parent / "uploaded_docs"
        self.uploaded_docs_dir.mkdir(exist_ok=True)
        
        logger.info("IngestionService initialized successfully")
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            str: MD5 hash hex digest.
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _check_duplicate(self, file_hash: str) -> Optional[str]:
        """Check if a file with the given hash already exists in Neo4j.
        
        Args:
            file_hash: MD5 hash of the file.
            
        Returns:
            Optional[str]: Existing document ID if duplicate found, None otherwise.
        """
        try:
            check_query = """
            MATCH (d:Document {file_hash: $file_hash})
            RETURN d.id AS doc_id
            LIMIT 1
            """
            
            result, _, _ = self.db.driver.execute_query(
                check_query,
                {"file_hash": file_hash},
                database_="neo4j"
            )
            
            if result:
                doc_id = result[0]["doc_id"]
                logger.info(f"Duplicate file detected. Existing doc_id: {doc_id}")
                return doc_id
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking for duplicate: {str(e)}")
            # If check fails, proceed with ingestion
            return None
    
    def ingest_pdf(self, file_path: str, file_name: str) -> Dict[str, Any]:
        """Ingest a PDF file and store it in Neo4j with hierarchical structure.
        
        Process:
        1. Calculate MD5 hash and check for duplicates
        2. If duplicate exists, return existing doc_id
        3. Save file to uploaded_docs directory
        4. Generate unique document ID (UUID)
        5. Load PDF page-by-page, preserving page metadata
        6. Split into chunks with overlap
        7. Generate embeddings for each chunk
        8. Store Document node and Chunk nodes in Neo4j
        9. Create BELONGS_TO relationships using batch UNWIND
        
        Args:
            file_path: Path to the PDF file to process.
            file_name: Name of the file (for Document node).
            
        Returns:
            dict: Summary with 'doc_id', 'chunk_count', 'status', 'file_name', 
                  and 'is_duplicate' (True if duplicate was found).
            
        Raises:
            FileNotFoundError: If the PDF file does not exist.
            Exception: If processing or storage fails.
        """
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Ingesting PDF: {file_path} (name: {file_name})")
        
        try:
            # Step 1: Calculate file hash and check for duplicates
            file_hash = self._calculate_file_hash(pdf_path)
            logger.info(f"File hash: {file_hash}")
            
            existing_doc_id = self._check_duplicate(file_hash)
            if existing_doc_id:
                logger.info(f"Skipping ingestion - duplicate file found. Doc ID: {existing_doc_id}")
                return {
                    "doc_id": existing_doc_id,
                    "chunk_count": 0,
                    "status": "duplicate",
                    "file_name": file_name,
                    "is_duplicate": True
                }
            
            # Step 2: Save file to uploaded_docs directory for static serving
            safe_filename = "".join(c for c in file_name if c.isalnum() or c in "._-")
            if not safe_filename:
                safe_filename = "uploaded_file.pdf"
            
            saved_file_path = self.uploaded_docs_dir / safe_filename
            # If file already exists with same name, add hash suffix
            if saved_file_path.exists():
                name_stem = saved_file_path.stem
                name_suffix = saved_file_path.suffix
                saved_file_path = self.uploaded_docs_dir / f"{name_stem}_{file_hash[:8]}{name_suffix}"
            
            shutil.copy2(pdf_path, saved_file_path)
            logger.info(f"Saved file to: {saved_file_path}")
            
            # Step 3: Generate unique document ID
            doc_id = str(uuid.uuid4())
            logger.info(f"Generated document ID: {doc_id}")
            
            # Step 4: Load PDF page-by-page with metadata
            loader = PyPDFLoader(str(saved_file_path))
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} pages from PDF")
            
            # Ensure page metadata is preserved
            for i, doc in enumerate(documents):
                if "page" not in doc.metadata:
                    doc.metadata["page"] = i
                # Add source information
                doc.metadata["source"] = file_name
            
            # Step 5: Split into chunks
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"Split into {len(chunks)} chunks")
            
            if not chunks:
                raise ValueError("No chunks generated from PDF")
            
            # Step 6: Generate embeddings for all chunks
            logger.info("Generating embeddings for chunks...")
            chunk_texts = [chunk.page_content for chunk in chunks]
            embeddings_list = self.embeddings.embed_documents(chunk_texts)
            logger.info(f"Generated {len(embeddings_list)} embeddings")
            
            # Step 7: Prepare chunk data for batch insert
            chunk_data = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings_list)):
                chunk_id = str(uuid.uuid4())
                page_num = chunk.metadata.get("page", 0)
                source = chunk.metadata.get("source", file_name)
                
                chunk_data.append({
                    "chunk_id": chunk_id,
                    "text": chunk.page_content,
                    "page": int(page_num),
                    "source": source,
                    "embedding": embedding
                })
            
            # Step 8: Store in Neo4j using batch UNWIND (with file_hash)
            self._store_document_and_chunks(doc_id, file_name, chunk_data, file_hash, saved_file_path.name)
            
            logger.info(
                f"Ingestion complete. Document ID: {doc_id}, "
                f"Chunks created: {len(chunk_data)}"
            )
            
            return {
                "doc_id": doc_id,
                "chunk_count": len(chunk_data),
                "status": "success",
                "file_name": file_name,
                "is_duplicate": False,
                "saved_file_name": saved_file_path.name
            }
            
        except Exception as e:
            logger.error(f"Error ingesting PDF {file_path}: {str(e)}", exc_info=True)
            raise
    
    def _store_document_and_chunks(
        self, 
        doc_id: str, 
        file_name: str, 
        chunk_data: List[Dict[str, Any]],
        file_hash: str,
        saved_file_name: str
    ) -> None:
        """Store Document node and Chunk nodes in Neo4j using batch operations.
        
        Uses UNWIND for efficient batch insertion of chunks and relationships.
        
        Args:
            doc_id: Unique document identifier (UUID).
            file_name: Name of the document.
            chunk_data: List of chunk dictionaries with id, text, page, source, embedding.
            file_hash: MD5 hash of the file for duplicate detection.
            saved_file_name: Name of the saved file in uploaded_docs directory.
            
        Raises:
            Exception: If database operation fails.
        """
        try:
            # Create Document node with file_hash
            create_doc_query = """
            MERGE (d:Document {id: $doc_id})
            SET d.name = $file_name,
                d.file_hash = $file_hash,
                d.saved_file_name = $saved_file_name,
                d.created_at = timestamp()
            RETURN d
            """
            
            self.db.driver.execute_query(
                create_doc_query,
                {
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "file_hash": file_hash,
                    "saved_file_name": saved_file_name
                },
                database_="neo4j"
            )
            logger.info(f"Created Document node: {doc_id} with hash: {file_hash}")
            
            # Batch create Chunk nodes and relationships using UNWIND
            create_chunks_query = """
            UNWIND $chunks AS chunk
            MATCH (d:Document {id: $doc_id})
            CREATE (c:Chunk {
                id: chunk.chunk_id,
                text: chunk.text,
                page: chunk.page,
                source: chunk.source,
                embedding: chunk.embedding
            })
            CREATE (c)-[:BELONGS_TO]->(d)
            RETURN count(c) AS chunk_count
            """
            
            result, _, _ = self.db.driver.execute_query(
                create_chunks_query,
                {"doc_id": doc_id, "chunks": chunk_data},
                database_="neo4j"
            )
            
            chunk_count = result[0]["chunk_count"] if result else 0
            logger.info(f"Created {chunk_count} Chunk nodes with BELONGS_TO relationships")
            
        except Exception as e:
            logger.error(f"Error storing document and chunks: {str(e)}", exc_info=True)
            raise
    
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.db:
            self.db.close()
        logger.info("IngestionService closed")
