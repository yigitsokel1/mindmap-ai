"""Pydantic contracts for semantic grounded query API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SemanticQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: Optional[str] = None
    node_types: List[str] = Field(default_factory=list)
    max_evidence: int = Field(default=5, ge=1, le=20)
    include_citations: bool = True


class SemanticEvidenceItem(BaseModel):
    relation_type: str
    page: Optional[int] = None
    snippet: str = ""
    section: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    related_node_ids: List[str] = Field(default_factory=list)
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    citation_label: Optional[str] = None
    reference_entry_id: Optional[str] = None


class RelatedNodeItem(BaseModel):
    id: str
    type: str
    display_name: str


class CitationItem(BaseModel):
    label: str
    reference_entry_id: Optional[str] = None
    page: Optional[int] = None
    document_name: Optional[str] = None


class MatchedEntityItem(BaseModel):
    id: str
    type: str
    display_name: str


class QueryExplanation(BaseModel):
    why_these_entities: List[str] = Field(default_factory=list)
    why_this_evidence: List[str] = Field(default_factory=list)
    reasoning_path: List[str] = Field(default_factory=list)
    selected_sections: List[str] = Field(default_factory=list)
    selection_signals: List[str] = Field(default_factory=list)


class SemanticQueryAnswer(BaseModel):
    answer: str
    query_intent: str = "SUMMARY"
    matched_entities: List[MatchedEntityItem] = Field(default_factory=list)
    evidence: List[SemanticEvidenceItem] = Field(default_factory=list)
    related_nodes: List[RelatedNodeItem] = Field(default_factory=list)
    citations: List[CitationItem] = Field(default_factory=list)
    explanation: QueryExplanation = Field(default_factory=QueryExplanation)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limited_evidence: bool = False
    uncertainty_signal: bool = False
    uncertainty_reason: Optional[str] = None
    mode: Literal["semantic_grounded"] = "semantic_grounded"
