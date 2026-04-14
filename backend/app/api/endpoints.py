"""API endpoints for the GraphRAG system.

This module defines the FastAPI routes for chat queries, PDF ingestion, and graph data retrieval.
"""

import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel

from backend.app.core.db import Neo4jDatabase
from backend.app.services.ingestion import IngestionService
from backend.app.services.retrieval import GraphRAGService
from backend.app.services.extraction.pipeline import ExtractionPipeline
from backend.app.services.ingestion.semantic_ingestion_service import SemanticIngestionService

# Create router
router = APIRouter()


# Pydantic models for request bodies
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    question: str
    doc_id: Optional[str] = None  # Optional document ID to filter search
    use_vector_search: bool = True  # Use vector search (True) or graph query (False)
    top_k: int = 5  # Number of top chunks to retrieve


# Note: IngestRequest is no longer used - we use UploadFile instead
# Keeping for backward compatibility if needed
class IngestRequest(BaseModel):
    """Request model for ingestion endpoint (legacy - use file upload instead)."""
    file_path: str = "data/attention-is-all-you-need-paper.pdf"
    file_name: Optional[str] = None


@router.post("/chat")
async def chat(request: ChatRequest):
    """Handle chat queries using GraphRAGService with optional document filtering.
    
    Args:
        request: ChatRequest containing the user's question and optional filters.
        
    Returns:
        dict: Response with 'result' (answer text), 'sources' (citations), 
              and optionally 'related_node_ids' (list of node IDs).
        
    Raises:
        HTTPException: If query processing fails.
    """
    try:
        service = GraphRAGService()
        # Include node IDs in the response for frontend highlighting
        result = service.answer_question(
            query=request.question,
            include_node_ids=True,
            doc_id=request.doc_id,
            use_vector_search=request.use_vector_search,
            top_k=request.top_k
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


def process_pdf_and_close(file_path: str, file_name: str):
    """Wrapper function to ingest PDF and close service.
    
    This function is used in BackgroundTasks to ensure the service
    is properly closed after processing.
    
    Args:
        file_path: Path to the PDF file to process.
        file_name: Name of the file (if not provided, extracted from path).
    """
    from pathlib import Path
    
    # Extract file name from path if not provided
    if not file_name:
        file_name = Path(file_path).name
    
    service = IngestionService()
    try:
        result = service.ingest_pdf(file_path, file_name)
        return result
    finally:
        service.close()


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(..., description="PDF file to ingest"),
    mode: str = "semantic",
):
    """Ingest a PDF file through the semantic KG extraction pipeline.

    Primary path (mode=semantic): PDF → parse → passages → extraction → graph
    Legacy path (mode=legacy): PDF → chunks → embeddings → vector store

    Args:
        file: Uploaded PDF file (multipart/form-data).
        mode: "semantic" (default) or "legacy".

    Returns:
        dict: Ingestion result with extraction diagnostics.
    """
    logger = logging.getLogger(__name__)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save to temp file
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
    if not safe_filename:
        safe_filename = "uploaded_file.pdf"

    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(
        temp_dir, f"mindmap_ai_{os.urandom(8).hex()}_{safe_filename}"
    )

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        original_filename = file.filename

        if mode == "legacy":
            # Legacy chunk/embedding path
            service = IngestionService()
            try:
                result = service.ingest_pdf(temp_file_path, original_filename)
                if result.get("saved_file_name"):
                    result["static_url"] = f"/static/{result['saved_file_name']}"
                return result
            finally:
                service.close()
        else:
            # Semantic KG extraction path (default)
            service = SemanticIngestionService()
            result = service.ingest_pdf(temp_file_path, original_filename)

            response = result.to_dict()
            if result.saved_file_name:
                response["static_url"] = f"/static/{result.saved_file_name}"
            return response

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning("Failed to remove temp file %s: %s", temp_file_path, e)


class ExtractRequest(BaseModel):
    """Request model for extraction endpoint."""
    text: str
    document_id: str = "test_doc"


@router.post("/extract")
async def extract_text(request: ExtractRequest):
    """Run the extraction pipeline on raw text.

    Splits text into passages, extracts entities and relations via LLM,
    and writes them to Neo4j. This is a convenience endpoint for testing;
    production ingestion should use POST /ingest with a PDF file.

    Args:
        request: ExtractRequest with text and optional document_id.

    Returns:
        dict: Pipeline result with extraction statistics.
    """
    import uuid
    from backend.app.schemas.passage import PassageRecord
    from backend.app.services.parsing.passage_splitter import PassageSplitter

    try:
        # Build passages from raw text (no page info available)
        splitter = PassageSplitter()
        raw_passages = splitter.split(request.text)
        passages = [
            PassageRecord(
                passage_id=f"pass:{uuid.uuid4().hex[:12]}",
                document_id=request.document_id,
                index=i,
                text=text,
                page_number=0,
            )
            for i, text in enumerate(raw_passages)
        ]

        pipeline = ExtractionPipeline()
        result = pipeline.run(request.document_id, passages)

        return {
            "status": "ok",
            "document_id": result.document_id,
            "pages_total": result.pages_total,
            "passages_total": result.passages_total,
            "passages_succeeded": result.passages_succeeded,
            "passages_failed": result.passages_failed,
            "entities_total": result.entities_total,
            "relations_total": result.relations_total,
            "evidence_total": result.evidence_total,
            "entities_dropped": result.entities_dropped,
            "relations_dropped": result.relations_dropped,
            "errors": result.errors,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}",
        )


@router.get("/graph")
async def get_graph(node_ids: str = None):
    """Retrieve graph data from Neo4j for visualization.
    
    Returns graph data in a format compatible with react-force-graph:
    - nodes: List of nodes with id, label, and name properties
    - links: List of relationships with source, target, and type properties
    
    Returns:
        dict: Graph data with nodes and links arrays.
        
    Raises:
        HTTPException: If database query fails.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    db = None
    try:
        db = Neo4jDatabase()
        
        # Connect if not already connected
        if not db.driver:
            try:
                db.connect()
            except Exception as conn_error:
                logger.error(f"Failed to connect to Neo4j: {str(conn_error)}", exc_info=True)
                raise HTTPException(
                    status_code=503,
                    detail=f"Database connection failed: {str(conn_error)}"
                )
        
        if not db.driver:
            logger.error("Neo4j driver is not available after connect attempt")
            raise HTTPException(
                status_code=503,
                detail="Database connection not available. Please ensure Neo4j is connected."
            )
        
        # Query to get all nodes and their relationships
        # If specific node_ids are provided, fetch those nodes and their neighborhood
        if node_ids:
            import logging
            logger = logging.getLogger(__name__)
            
            try:
                # Parse comma-separated node IDs
                node_id_list = [nid.strip() for nid in node_ids.split(",")]
                logger.info(f"Fetching nodes by IDs: {len(node_id_list)} IDs requested")
                
                # Build query using UNWIND for better compatibility
                # Match nodes by element_id and get their relationships
                query_nodes = """
                UNWIND $node_ids AS node_id
                MATCH (n)
                WHERE elementId(n) = node_id
                OPTIONAL MATCH (n)-[r]-(m)
                RETURN DISTINCT n, r, m
                LIMIT 5000
                """
                
                # Single query for nodes and relationships with parameters
                records, summary, keys = db.driver.execute_query(
                    query_nodes, 
                    {"node_ids": node_id_list},
                    database_="neo4j"
                )
                
                logger.info(f"Query returned {len(records)} records")
                
                nodes_map: Dict[str, Dict[str, Any]] = {}
                links: List[Dict[str, Any]] = []
                
                for record in records:
                    node_n = record.get("n")
                    rel = record.get("r")
                    node_m = record.get("m")
                    
                    # Process source node
                    if node_n:
                        try:
                            node_n_id = str(node_n.element_id)
                        except AttributeError:
                            node_n_id = str(node_n.id)
                        
                        if node_n_id not in nodes_map:
                            labels = list(node_n.labels)
                            props = dict(node_n.items())
                            # Create node with all properties from Neo4j
                            node_data = {
                                "id": node_n_id,
                                "label": labels[0] if labels else "Node",
                                "name": props.get("id", props.get("name", props.get("title", node_n_id)))
                            }
                            # Add all other properties from Neo4j
                            for key, value in props.items():
                                if key not in node_data:
                                    node_data[key] = value
                            nodes_map[node_n_id] = node_data
                    
                    # Process relationship and target node
                    if rel and node_m:
                        try:
                            node_m_id = str(node_m.element_id)
                        except AttributeError:
                            node_m_id = str(node_m.id)
                        
                        if node_m_id not in nodes_map:
                            labels = list(node_m.labels)
                            props = dict(node_m.items())
                            # Create node with all properties from Neo4j
                            node_data = {
                                "id": node_m_id,
                                "label": labels[0] if labels else "Node",
                                "name": props.get("id", props.get("name", props.get("title", node_m_id)))
                            }
                            # Add all other properties from Neo4j
                            for key, value in props.items():
                                if key not in node_data:
                                    node_data[key] = value
                            nodes_map[node_m_id] = node_data
                        
                        try:
                            source_id = str(rel.start_node.element_id)
                            target_id = str(rel.end_node.element_id)
                        except AttributeError:
                            source_id = str(rel.start_node.id)
                            target_id = str(rel.end_node.id)
                        
                        links.append({
                            "source": source_id,
                            "target": target_id,
                            "type": rel.type
                        })
                
                logger.info(f"Returning {len(nodes_map)} nodes and {len(links)} links")
                return {"nodes": list(nodes_map.values()), "links": links}
                
            except Exception as e:
                logger.error(f"Error fetching nodes by IDs: {e}", exc_info=True)
                # Fall back to default query if specific node query fails
                pass
        
        # Default: get all Document and Chunk nodes with their relationships
        # Use separate queries for better reliability
        try:
            # First, get all Document and Chunk nodes
            nodes_query = """
            MATCH (n)
            WHERE n:Document OR n:Chunk
            RETURN n
            LIMIT 5000
            """
            
            node_records, _, _ = db.driver.execute_query(
                nodes_query,
                database_="neo4j"
            )
            
            # Then get relationships between these nodes - specifically BELONGS_TO
            # Query both directions to ensure we catch all relationships
            rels_query = """
            MATCH (c:Chunk)-[r:BELONGS_TO]->(d:Document)
            RETURN c, r, d
            LIMIT 5000
            """
            
            rel_records, summary, keys = db.driver.execute_query(
                rels_query,
                database_="neo4j"
            )
            
            # Force print to stdout to ensure visibility
            print(f"GRAPH DEBUG: Found {len(rel_records)} BELONGS_TO relationships in database")
            print(f"GRAPH DEBUG: Query keys: {keys}")
            print(f"GRAPH DEBUG: Summary: {summary}")
            
            logger.info(f"GRAPH DEBUG: Found {len(rel_records)} BELONGS_TO relationships in database")
            logger.info(f"GRAPH DEBUG: Query keys: {keys}")
            
            # Log first few records if they exist
            if len(rel_records) > 0:
                first_record = rel_records[0]
                print(f"GRAPH DEBUG: First rel_record: {first_record}")
                print(f"GRAPH DEBUG: First rel_record keys: {list(first_record.keys()) if hasattr(first_record, 'keys') else 'no keys'}")
                logger.info(f"GRAPH DEBUG: First rel_record sample: {first_record}")
            else:
                print("GRAPH DEBUG: No relationship records found from query!")
                logger.warning("GRAPH DEBUG: No relationship records found from query!")
            
            # If no relationships found, try checking if they exist at all
            if len(rel_records) == 0:
                check_query = """
                MATCH (c:Chunk)-[r:BELONGS_TO]->(d:Document)
                RETURN count(r) as rel_count
                """
                check_result, _, _ = db.driver.execute_query(
                    check_query,
                    database_="neo4j"
                )
                rel_count = check_result[0]["rel_count"] if check_result else 0
                logger.warning(f"No relationships found in query result, but count query shows {rel_count} relationships exist")
            
            # Combine results - use a set to track processed nodes
            records = []
            processed_node_ids = set()
            
            # First, add all nodes
            for record in node_records:
                node = record["n"]
                try:
                    node_id = str(node.element_id)
                except AttributeError:
                    node_id = str(node.id)
                
                if node_id not in processed_node_ids:
                    records.append({
                        "n": node,
                        "r": None,
                        "m": None
                    })
                    processed_node_ids.add(node_id)
            
            # Then add relationships (they include nodes too)
            for idx, record in enumerate(rel_records):
                # Neo4j driver returns Record objects - access like dict with key name
                # Query returns: c, r, d (Chunk, Relationship, Document)
                try:
                    # Debug first record to see structure
                    if idx == 0:
                        logger.info(f"First relationship record keys: {list(record.keys()) if hasattr(record, 'keys') else 'no keys method'}")
                        logger.info(f"First relationship record type: {type(record)}")
                        logger.info(f"First relationship record values: {list(record.values()) if hasattr(record, 'values') else 'no values method'}")
                    
                    node_c = record["c"]  # Chunk node (source)
                    rel = record["r"]     # Relationship
                    node_d = record["d"]  # Document node (target)
                    
                    # Debug first record to see structure
                    if idx == 0:
                        logger.info(f"First record - node_c type: {type(node_c)}, rel type: {type(rel)}, node_d type: {type(node_d)}")
                        logger.info(f"First record - rel value: {rel}, rel is None: {rel is None}")
                        logger.info(f"First record - node_c is None: {node_c is None}, node_d is None: {node_d is None}")
                        if rel is not None:
                            logger.info(f"First record - rel.start_node: {rel.start_node}, rel.end_node: {rel.end_node}, rel.type: {rel.type}")
                    
                    # Check for None explicitly (not truthiness, as relationship objects should always be truthy)
                    if node_c is not None and rel is not None and node_d is not None:
                        # Add relationship record - we'll use node_c and node_d directly for link source/target
                        rel_record = {
                            "n": node_c,
                            "r": rel,
                            "m": node_d
                        }
                        records.append(rel_record)
                        if idx < 3:  # Log first few successful additions
                            print(f"GRAPH DEBUG: Added relationship {idx} to records: c={type(node_c).__name__}, r={type(rel).__name__}, d={type(node_d).__name__}")
                            print(f"GRAPH DEBUG: Record dict keys: {list(rel_record.keys())}")
                            print(f"GRAPH DEBUG: Record dict['r'] check: {rel_record.get('r') is not None}, type: {type(rel_record.get('r'))}")
                            print(f"GRAPH DEBUG: Record dict after append - records[{len(records)-1}]['r']: {records[-1].get('r') is not None}")
                    else:
                        if idx < 3:  # Only log first 3 for debugging
                            print(f"GRAPH DEBUG: Skipping relationship {idx}: c={node_c is not None}, r={rel is not None}, d={node_d is not None}")
                            logger.warning(f"Skipping relationship {idx}: c={node_c is not None}, r={rel is not None}, d={node_d is not None}")
                except (KeyError, AttributeError, TypeError) as e:
                    logger.error(f"Error accessing relationship record {idx}: {e}, record type: {type(record)}, record: {record}")
            
            print(f"GRAPH DEBUG: Total records after adding relationships: {len(records)}")
            print(f"GRAPH DEBUG: Records with 'r' key: {sum(1 for r in records if 'r' in r and r['r'] is not None)}")
            
            # Debug: Check a few relationship records directly
            rel_record_count = 0
            for r_idx, r in enumerate(records):
                if r.get("r") is not None:
                    rel_record_count += 1
                    if rel_record_count <= 3:
                        print(f"GRAPH DEBUG: Found relationship record at index {r_idx}: r={r.get('r') is not None}, type(r['r'])={type(r.get('r'))}")
            
            print(f"GRAPH DEBUG: Total relationship records found in list: {rel_record_count}")
            
        except Exception as query_error:
            logger.error(f"Query execution error: {str(query_error)}", exc_info=True)
            # Try with a simpler query
            query_simple = """
            MATCH (n:Document)
            RETURN n
            LIMIT 100
            """
            try:
                simple_records, _, _ = db.driver.execute_query(
                    query_simple,
                    database_="neo4j"
                )
                # If simple query works, return empty graph (at least connection works)
                logger.info("Simple query succeeded, returning empty graph")
                return {"nodes": [], "links": []}
            except Exception as simple_error:
                logger.error(f"Simple query also failed: {str(simple_error)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Database query failed: {str(query_error)}"
                )
        
        # Extract unique nodes and relationships
        nodes_map: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []
        
        # Process all nodes and relationships
        processed_with_links = 0
        skipped_no_rel = 0
        skipped_no_nodes = 0
        for idx, record in enumerate(records):
            node_n = record.get("n")
            rel = record.get("r")
            node_m = record.get("m")
            
            # Debug first few records and relationship records
            if idx < 5 or (252 <= idx < 257):  # First 5 node records, or first 5 relationship records
                print(f"GRAPH DEBUG: Processing record {idx}: has_n={node_n is not None}, has_r={rel is not None}, has_m={node_m is not None}")
                if idx >= 252:  # This should be a relationship record
                    print(f"GRAPH DEBUG: Record {idx} keys: {list(record.keys())}")
                    print(f"GRAPH DEBUG: Record {idx}['r'] type: {type(record.get('r'))}, value: {record.get('r')}")
                    print(f"GRAPH DEBUG: Record {idx} rel type: {type(rel)}, value: {rel}, bool(rel): {bool(rel)}")
                    print(f"GRAPH DEBUG: Record {idx} node_n: {node_n is not None}, node_m: {node_m is not None}")
            
            # Process source node
            if node_n:
                # Try elementId() first (Neo4j 5.x), fallback to id() (older versions)
                try:
                    node_id = str(node_n.element_id)
                except AttributeError:
                    node_id = str(node_n.id)
                
                if node_id not in nodes_map:
                    labels = list(node_n.labels)
                    props = dict(node_n.items())
                    
                    # Determine node type and label
                    node_type = labels[0] if labels else "Node"
                    
                    if node_type == "Document":
                        node_label = props.get("name", props.get("id", node_id))
                    elif node_type == "Chunk":
                        # Use first 50 characters of text as label
                        text = props.get("text", "")
                        node_label = text[:50] + "..." if len(text) > 50 else text
                        if not node_label:
                            node_label = f"Chunk {props.get('id', node_id)[:8]}"
                    else:
                        node_label = props.get("id", props.get("name", node_id))
                    
                    node_data = {
                        "id": node_id,
                        "label": node_type,
                        "name": node_label,
                        "type": node_type.lower()
                    }
                    
                    # Add page number for chunks
                    if node_type == "Chunk" and "page" in props:
                        node_data["page"] = props["page"]
                    
                    # Add source for chunks
                    if node_type == "Chunk" and "source" in props:
                        node_data["source"] = props["source"]
                    
                    nodes_map[node_id] = node_data
            
            # Process relationship and target node
            # Use explicit None checks instead of truthiness for better debugging
            if rel is not None and node_m is not None:
                # Try elementId() first (Neo4j 5.x), fallback to id() (older versions)
                try:
                    node_m_id = str(node_m.element_id)
                except AttributeError:
                    node_m_id = str(node_m.id)
                
                if node_m_id not in nodes_map:
                    labels = list(node_m.labels)
                    props = dict(node_m.items())
                    
                    node_type = labels[0] if labels else "Node"
                    
                    if node_type == "Document":
                        node_label = props.get("name", props.get("id", node_m_id))
                    elif node_type == "Chunk":
                        text = props.get("text", "")
                        node_label = text[:50] + "..." if len(text) > 50 else text
                        if not node_label:
                            node_label = f"Chunk {props.get('id', node_m_id)[:8]}"
                    else:
                        node_label = props.get("id", props.get("name", node_m_id))
                    
                    node_data = {
                        "id": node_m_id,
                        "label": node_type,
                        "name": node_label,
                        "type": node_type.lower()
                    }
                    
                    if node_type == "Chunk":
                        if "page" in props:
                            node_data["page"] = props["page"]
                        if "source" in props:
                            node_data["source"] = props["source"]
                    
                    nodes_map[node_m_id] = node_data
                
                # Add link - use node_n (source) and node_m (target) directly instead of rel.start_node/end_node
                if node_n is not None and node_m is not None:
                    try:
                        # Get source node ID from node_n (Chunk - source)
                        try:
                            source_id = str(node_n.element_id)
                        except AttributeError:
                            source_id = str(node_n.id)
                        
                        # Get target node ID from node_m (Document - target)
                        try:
                            target_id = str(node_m.element_id)
                        except AttributeError:
                            target_id = str(node_m.id)
                        
                        links.append({
                            "source": source_id,
                            "target": target_id,
                            "type": rel.type
                        })
                        processed_with_links += 1
                    except Exception as link_error:
                        print(f"GRAPH DEBUG: Error creating link: {link_error}")
                        logger.error(f"Error creating link from relationship: {link_error}", exc_info=True)
                else:
                    skipped_no_nodes += 1
                    if skipped_no_nodes <= 3:
                        print(f"GRAPH DEBUG: Skipping link creation - node_n={node_n is not None}, node_m={node_m is not None}")
            else:
                skipped_no_rel += 1
        
        # Convert nodes_map to list
        nodes = list(nodes_map.values())
        
        print(f"GRAPH DEBUG: Link creation summary - processed_with_links={processed_with_links}, skipped_no_rel={skipped_no_rel}, skipped_no_nodes={skipped_no_nodes}")
        logger.info(f"GRAPH DEBUG: Returning {len(nodes)} nodes and {len(links)} links")
        logger.info(f"GRAPH DEBUG: records list has {len(records)} items")
        logger.info(f"GRAPH DEBUG: records with relationships: {sum(1 for r in records if r.get('r') is not None)}")
        print(f"GRAPH DEBUG: Final link count: {len(links)}")
        
        return {
            "nodes": nodes,
            "links": links
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving graph data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving graph data: {str(e)}"
        )
    # Note: Don't close db here - it's a singleton and other endpoints need it
