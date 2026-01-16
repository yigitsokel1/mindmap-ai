"""API endpoints for the GraphRAG system.

This module defines the FastAPI routes for chat queries, PDF ingestion, and graph data retrieval.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Any

from backend.app.core.db import Neo4jDatabase
from backend.app.services.ingestion import IngestionService
from backend.app.services.retrieval import GraphRAGService

# Create router
router = APIRouter()


# Pydantic models for request bodies
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    question: str


class IngestRequest(BaseModel):
    """Request model for ingestion endpoint."""
    file_path: str = "data/attention-is-all-you-need-paper.pdf"


@router.post("/chat")
async def chat(request: ChatRequest):
    """Handle chat queries using GraphRAGService.
    
    Args:
        request: ChatRequest containing the user's question.
        
    Returns:
        dict: Response with 'result' (answer text) and 'related_node_ids' (list of node IDs).
        
    Raises:
        HTTPException: If query processing fails.
    """
    try:
        service = GraphRAGService()
        # Include node IDs in the response for frontend highlighting
        result = service.answer_question(request.question, include_node_ids=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


def process_pdf_and_close(file_path: str):
    """Wrapper function to process PDF and close service.
    
    This function is used in BackgroundTasks to ensure the service
    is properly closed after processing.
    
    Args:
        file_path: Path to the PDF file to process.
    """
    service = IngestionService()
    try:
        service.process_pdf(file_path)
    finally:
        service.close()


@router.post("/ingest")
async def ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    """Handle PDF ingestion using IngestionService.
    
    Args:
        request: IngestRequest containing the file path.
        background_tasks: FastAPI BackgroundTasks for async processing.
        
    Returns:
        dict: Confirmation message that ingestion has started.
        
    Raises:
        HTTPException: If ingestion setup fails.
    """
    try:
        # Add PDF processing to background tasks
        background_tasks.add_task(process_pdf_and_close, request.file_path)
        return {
            "message": "PDF ingestion started",
            "file_path": request.file_path,
            "status": "processing"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting ingestion: {str(e)}")


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
    try:
        db = Neo4jDatabase()
        
        if not db.driver:
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
                        node_n_id = str(node_n.element_id)
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
                        node_m_id = str(node_m.element_id)
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
                        
                        links.append({
                            "source": str(rel.start_node.element_id),
                            "target": str(rel.end_node.element_id),
                            "type": rel.type
                        })
                
                logger.info(f"Returning {len(nodes_map)} nodes and {len(links)} links")
                return {"nodes": list(nodes_map.values()), "links": links}
                
            except Exception as e:
                logger.error(f"Error fetching nodes by IDs: {e}", exc_info=True)
                # Fall back to default query if specific node query fails
                pass
        
        # Default: get all nodes and their relationships
        query_nodes = "MATCH (n) RETURN n LIMIT 1000"
        query_rels = "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 2000"
        
        # Get all nodes first
        node_records, _, _ = db.driver.execute_query(
            query_nodes,
            database_="neo4j"
        )
        
        # Get all relationships
        rel_records, _, _ = db.driver.execute_query(
            query_rels,
            database_="neo4j"
        )
        
        # Extract unique nodes and relationships
        nodes_map: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []
        
        # Process all nodes first
        for record in node_records:
            node = record["n"]
            node_id = str(node.element_id)
            
            if node_id not in nodes_map:
                labels = list(node.labels)
                props = dict(node.items())
                # Create node with all properties from Neo4j
                node_data = {
                    "id": node_id,
                    "label": labels[0] if labels else "Node",
                    "name": props.get("id", props.get("name", props.get("title", node_id)))
                }
                # Add all other properties from Neo4j
                for key, value in props.items():
                    if key not in node_data and value is not None:
                        node_data[key] = value
                
                # Debug logging for first few nodes
                import logging
                logger = logging.getLogger(__name__)
                if len(nodes_map) < 3:  # Log first 3 nodes
                    logger.info(f"Node {len(nodes_map)}: label={labels[0] if labels else 'None'}, props_keys={list(props.keys())}, node_data_keys={list(node_data.keys())}")
                
                nodes_map[node_id] = node_data
        
        # Then process relationships
        for record in rel_records:
            # Process source node (n)
            node_n = record["n"]
            node_n_id = str(node_n.element_id)
            
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
            
            # Process target node (m)
            node_m = record["m"]
            node_m_id = str(node_m.element_id)
            
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
            
            # Process relationship (r)
            rel = record["r"]
            rel_type = rel.type
            rel_start_id = str(rel.start_node.element_id)
            rel_end_id = str(rel.end_node.element_id)
            
            links.append({
                "source": rel_start_id,
                "target": rel_end_id,
                "type": rel_type
            })
        
        # Convert nodes_map to list
        nodes = list(nodes_map.values())
        
        # Debug: Log sample node structure
        if nodes:
            import logging
            logger = logging.getLogger(__name__)
            sample_node = nodes[0]
            logger.info(f"Sample node structure: {sample_node}")
            logger.info(f"Sample node keys: {list(sample_node.keys())}")
            
            # Also log a Paper node if available
            paper_node = next((n for n in nodes if n.get("label") == "Paper"), None)
            if paper_node:
                logger.info(f"Paper node found with keys: {list(paper_node.keys())}")
                logger.info(f"Paper node full structure: {paper_node}")
        
        return {
            "nodes": nodes,
            "links": links
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving graph data: {str(e)}")
