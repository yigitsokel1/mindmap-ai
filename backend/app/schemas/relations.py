"""Relation schemas for KG extraction output validation."""

from pydantic import BaseModel, Field


VALID_RELATION_TYPES = {
    "WROTE",
    "AFFILIATED_WITH",
    "MENTIONS",
    "INTRODUCES",
    "USES",
    "EVALUATED_ON",
    "MEASURED_BY",
    "ABOUT",
}


class Relation(BaseModel):
    """Schema for an extracted relation between two entities."""

    type: str
    source: str
    target: str
    confidence: float = Field(ge=0, le=1)
