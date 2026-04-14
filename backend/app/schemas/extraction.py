"""Top-level extraction result schema.

This is the contract between the LLM extractor and the rest of the pipeline.
"""

from typing import List

from pydantic import BaseModel

from .entities import BaseEntity
from .relations import Relation


class ExtractionResult(BaseModel):
    """Complete extraction output from a single passage."""

    entities: List[BaseEntity] = []
    relations: List[Relation] = []
