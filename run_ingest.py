"""Script to manually run PDF ingestion using IngestionService.

This script processes a PDF file and extracts knowledge graph to Neo4j.
"""

import logging
import sys
from pathlib import Path

from backend.app.services.ingestion import IngestionService

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
        
        # Process the PDF
        result = service.process_pdf(str(pdf_path))
        
        # Print results
        print(f"\nProcessing completed successfully!")
        print(f"Nodes created: {result['nodes']}")
        print(f"Relationships created: {result['relationships']}")
        print("\nSuccess! Graph created.")
        
        # Cleanup
        service.close()
        
    except Exception as e:
        print(f"\nError processing PDF: {str(e)}")
        logging.exception("Detailed error information:")
        sys.exit(1)

if __name__ == "__main__":
    main()
