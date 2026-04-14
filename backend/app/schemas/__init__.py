"""Application schema exports."""

from .citation import CitationLinkRecord, InlineCitationRecord
from .document_structure import ReferenceRecord, SectionRecord
from .entities import BaseEntity
from .extraction import ExtractionResult
from .passage import PassageRecord
from .relations import Relation

__all__ = [
    "CitationLinkRecord",
    "InlineCitationRecord",
    "ReferenceRecord",
    "SectionRecord",
    "BaseEntity",
    "ExtractionResult",
    "PassageRecord",
    "Relation",
]
