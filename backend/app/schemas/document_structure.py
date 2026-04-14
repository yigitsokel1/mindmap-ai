"""Document structure schemas.

Models for section and reference metadata extracted
from document parsing. These carry structural context
that supports section-aware extraction and provenance.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SectionRecord(BaseModel):
    """A detected section within a document."""

    section_id: str          # "sec:{uuid_hex[:12]}"
    document_id: str
    title: str               # e.g., "3. Model Architecture"
    level: int = 1           # 1=top-level, 2=subsection
    ordinal: int             # 0-indexed position in document
    page_start: int = 0
    page_end: int = 0


class ReferenceRecord(BaseModel):
    """A single bibliographic reference entry."""

    reference_id: str        # "ref:{uuid_hex[:12]}"
    document_id: str
    raw_text: str            # Full reference text
    order: int               # Position in reference list (0-indexed)
    year: Optional[int] = None
    title_guess: Optional[str] = None
    authors_guess: list[str] = Field(default_factory=list)
    citation_key_numeric: Optional[int] = None
    citation_key_author_year: Optional[list[str]] = None
