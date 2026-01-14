"""FastAPI application entry point for the GraphRAG system.

This module initializes the FastAPI app, includes routers, and manages
database connections on startup/shutdown.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.endpoints import router
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
    title="MindMap-AI GraphRAG API",
    description="A GraphRAG system for ingesting academic PDFs and querying knowledge graphs",
    version="0.1.0",
    lifespan=lifespan
)

# Include API router with /api prefix
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Health check endpoint.
    
    Returns:
        dict: Health check message.
    """
    return {
        "message": "MindMap-AI GraphRAG API is running",
        "status": "healthy"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
