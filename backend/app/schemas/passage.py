"""Passage metadata schema.

A passage is the atomic extraction unit. This model carries
the passage text together with its structural context so that
provenance can trace back to the exact source location.
"""

from typing import Optional

from pydantic import BaseModel


class PassageRecord(BaseModel):
    """A passage with its structural metadata."""

    passage_id: str
    document_id: str
    index: int
    text: str
    page_number: int = 0
    section_title: Optional[str] = None
    section_id: Optional[str] = None
    content_type: str = "body"  # "body", "reference", "front_matter"
    char_start: Optional[int] = None
    char_end: Optional[int] = None
