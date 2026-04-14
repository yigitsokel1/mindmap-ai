"""Citation parsing and linking schemas.

Structured models for inline citation mentions and their
linkage to parsed reference entries.
"""

from typing import Optional

from pydantic import BaseModel, Field


class InlineCitationRecord(BaseModel):
    """A single inline citation mention found in a body passage."""

    citation_id: str
    document_id: str
    passage_id: str
    page_number: int
    raw_text: str
    citation_style: str
    start_char: int
    end_char: int
    reference_keys: Optional[list[str]] = None
    reference_labels: Optional[list[str]] = None


class CitationLinkRecord(BaseModel):
    """A match between an inline citation and a reference entry."""

    inline_citation_id: str
    reference_entry_id: str
    confidence: float = Field(ge=0.0, le=1.0)
