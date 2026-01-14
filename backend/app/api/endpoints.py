"""API endpoints for the GraphRAG system.

This module defines the FastAPI routes for chat queries and PDF ingestion.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from backend.app.services.ingestion import IngestionService
from backend.app.services.retrieval import GraphRAGService

# Create router
router = APIRouter()


# Pydantic models for request bodies
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    query: str


class IngestRequest(BaseModel):
    """Request model for ingestion endpoint."""
    file_path: str = "data/attention-is-all-you-need-paper.pdf"


@router.post("/chat")
async def chat(request: ChatRequest):
    """Handle chat queries using GraphRAGService.
    
    Args:
        request: ChatRequest containing the user's query.
        
    Returns:
        dict: The answer from GraphRAGService.
        
    Raises:
        HTTPException: If query processing fails.
    """
    try:
        service = GraphRAGService()
        result = service.answer_question(request.query)
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
