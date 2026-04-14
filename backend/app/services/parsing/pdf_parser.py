"""PDF parsing layer.

Extracts page-level text from PDF files using PyPDFLoader.
Produces PageRecord objects that preserve page number metadata.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader

logger = logging.getLogger(__name__)


@dataclass
class PageRecord:
    """A single page extracted from a PDF."""

    page_number: int  # 0-indexed
    text: str


def parse_pdf(file_path: str) -> list[PageRecord]:
    """Parse a PDF file into page records.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of PageRecord objects, one per page.

    Raises:
        FileNotFoundError: If the PDF file doesn't exist.
        ValueError: If no text could be extracted.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    loader = PyPDFLoader(str(path))
    documents = loader.load()

    pages: list[PageRecord] = []
    for i, doc in enumerate(documents):
        text = doc.page_content.strip()
        if not text:
            logger.debug("Skipping empty page %d", i)
            continue
        page_num = doc.metadata.get("page", i)
        pages.append(PageRecord(page_number=int(page_num), text=text))

    if not pages:
        raise ValueError(f"No text extracted from PDF: {file_path}")

    logger.info("Parsed %d pages from %s", len(pages), path.name)
    return pages
