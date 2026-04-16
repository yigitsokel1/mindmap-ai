"""Inspector node detail contract for explainability views."""

from typing import Dict, Optional

from pydantic import BaseModel


class NodeRelationItem(BaseModel):
    id: str
    type: str
    name: str


class NodeEvidenceItem(BaseModel):
    text: str
    passage_id: str
    document_id: str
    section: Optional[str] = None
    score: Optional[float] = None


class NodeCitationItem(BaseModel):
    title: str
    year: Optional[int] = None
    label: Optional[str] = None


class NodeRelations(BaseModel):
    incoming: list[NodeRelationItem]
    outgoing: list[NodeRelationItem]


class NodeRelationGroup(BaseModel):
    relation_type: str
    count: int
    items: list[NodeRelationItem]


class NodeGroupedRelations(BaseModel):
    incoming: list[NodeRelationGroup]
    outgoing: list[NodeRelationGroup]


class NodeDetail(BaseModel):
    id: str
    type: str
    name: str
    summary: str
    metadata: Dict[str, str | int | float | bool | None]
    relations: NodeRelations
    grouped_relations: NodeGroupedRelations
    evidences: list[NodeEvidenceItem]
    citations: list[NodeCitationItem]
    linked_canonical_entity: Optional[Dict[str, str | int | float | bool | None]] = None
    canonical_link_reason: Optional[str] = None
    canonical_link_confidence: Optional[float] = None
    canonical_aliases: list[str] = []
    canonical_alias_count: int = 0
    appears_in_documents: int = 0
    top_related_documents: list[str] = []
    document_distribution: list[Dict[str, str | int]] = []
