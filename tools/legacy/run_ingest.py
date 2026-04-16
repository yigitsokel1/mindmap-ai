"""Legacy ingestion debug script.

This helper exercises the legacy chunk/embedding ingestion path via
`IngestionService` for migration diagnostics.
For the primary semantic path, prefer `POST /api/ingest` (default mode).
"""

import logging
import sys
from pathlib import Path

from backend.app.legacy.services.ingestion.legacy_ingestion_service import IngestionService

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# PDF file path - adjust this to your PDF file
PDF_PATH = "data/attention-is-all-you-need-paper.pdf"

def main():
    """Run the ingestion service to process a PDF."""
    pdf_path = Path(PDF_PATH)
    print("Legacy ingestion diagnostic script. Primary path is POST /api/ingest (semantic mode).")
    
    # Check if PDF file exists
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {PDF_PATH}")
        print(f"Please check the file path and update PDF_PATH in the script.")
        sys.exit(1)
    
    print(f"Processing PDF: {PDF_PATH}")
    
    try:
        # Initialize the ingestion service
        # This will connect to Neo4j and initialize all components
        service = IngestionService()
        
        # Extract file name from path
        file_name = pdf_path.name
        
        # Ingest the PDF
        result = service.ingest_pdf(str(pdf_path), file_name)
        
        # Print results
        print(f"\n✅ Ingestion completed successfully!")
        print(f"📄 Document ID: {result['doc_id']}")
        print(f"📝 File Name: {result['file_name']}")
        print(f"🔢 Chunks created: {result['chunk_count']}")
        print(f"📊 Status: {result['status']}")
        print("\n✨ Success! Document and chunks stored in Neo4j.")
        
        # Cleanup
        service.close()
        
    except Exception as e:
        print(f"\nError processing PDF: {str(e)}")
        logging.exception("Detailed error information:")
        sys.exit(1)

if __name__ == "__main__":
    main()
