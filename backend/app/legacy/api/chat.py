"""Chat API endpoints.

Current chat path uses legacy retrieval while semantic chat is pending.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.legacy.services.legacy.retrieval import GraphRAGService

router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    question: str
    doc_id: Optional[str] = None
    use_vector_search: bool = True
    top_k: int = 5


@router.post("/chat")
async def chat(request: ChatRequest):
    """Handle chat queries via legacy retrieval path.

    Note:
        current chat path = legacy retrieval
        semantic query chat = pending
    """
    try:
        service = GraphRAGService()
        return service.answer_question(
            query=request.question,
            include_node_ids=True,
            doc_id=request.doc_id,
            use_vector_search=request.use_vector_search,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error processing query: {exc}") from exc
