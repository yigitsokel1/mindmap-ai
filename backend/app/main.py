"""FastAPI application entry point for the Semantic KG system.

This module initializes the FastAPI app, includes routers, and manages
database connections on startup/shutdown.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.router import router
from backend.app.core.db import Neo4jDatabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.
    
    Connects to Neo4j on startup and closes connection on shutdown.
    """
    # Startup: Connect to database
    db = Neo4jDatabase()
    db.connect()
    app.state.db = db
    yield
    # Shutdown: Close database connection
    if hasattr(app.state, 'db'):
        app.state.db.close()


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="MindMap-AI Semantic KG API",
    description="Semantic Knowledge Graph-based Research Copilot API",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router with /api prefix
app.include_router(router, prefix="/api")

# Create uploaded_docs directory if it doesn't exist
UPLOADED_DOCS_DIR = Path(__file__).parent.parent.parent / "uploaded_docs"
UPLOADED_DOCS_DIR.mkdir(exist_ok=True)

# Mount static files for PDF access
# This allows frontend to access PDFs via http://localhost:8000/static/filename.pdf
app.mount("/static", StaticFiles(directory=str(UPLOADED_DOCS_DIR)), name="static")


@app.get("/")
async def root():
    """Health check endpoint.
    
    Returns:
        dict: Health check message.
    """
    return {
        "message": "MindMap-AI Semantic KG API is running",
        "status": "healthy"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
