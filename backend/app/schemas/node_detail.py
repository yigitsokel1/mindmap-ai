"""Inspector node detail contract for explainability views."""

from pydantic import BaseModel


class NodeRelationItem(BaseModel):
    id: str
    type: str
    name: str


class NodeEvidenceItem(BaseModel):
    text: str
    passage_id: str
    document_id: str


class NodeCitationItem(BaseModel):
    title: str
    year: int


class NodeRelations(BaseModel):
    incoming: list[NodeRelationItem]
    outgoing: list[NodeRelationItem]


class NodeDetail(BaseModel):
    id: str
    type: str
    name: str
    summary: str
    relations: NodeRelations
    evidences: list[NodeEvidenceItem]
    citations: list[NodeCitationItem]
