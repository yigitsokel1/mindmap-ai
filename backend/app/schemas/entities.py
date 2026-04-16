"""Entity schemas for KG extraction output validation.

These Pydantic models define the strict shape that LLM extraction
must conform to. Every extracted entity passes through these models.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class BaseEntity(BaseModel):
    """Base schema for all extracted entities."""

    type: str
    name: str
    canonical_name: Optional[str] = None
    aliases: List[str] = []
    confidence: float = Field(ge=0, le=1)
    canonical_id: Optional[str] = None
    canonical_linked: Optional[bool] = None
    canonical_link_reason: Optional[str] = None
    canonical_link_confidence: Optional[float] = None
    canonical_created_new: Optional[bool] = None


class Concept(BaseEntity):
    type: str = "Concept"
    definition: Optional[str] = None


class Method(BaseEntity):
    type: str = "Method"
    description: Optional[str] = None


class Dataset(BaseEntity):
    type: str = "Dataset"
    domain: Optional[str] = None


class Metric(BaseEntity):
    type: str = "Metric"


class Task(BaseEntity):
    type: str = "Task"


class Author(BaseEntity):
    type: str = "Author"


class Institution(BaseEntity):
    type: str = "Institution"
    institution_type: Optional[str] = None


ENTITY_TYPE_MAP = {
    "Concept": Concept,
    "Method": Method,
    "Dataset": Dataset,
    "Metric": Metric,
    "Task": Task,
    "Author": Author,
    "Institution": Institution,
}

VALID_ENTITY_TYPES = set(ENTITY_TYPE_MAP.keys())
