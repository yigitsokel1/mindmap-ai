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
    cluster_key: Optional[str] = None


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


class CandidateEntity(BaseModel):
    entity_id: str
    name: str
    type: str
    score: float = 0.0
    match_reason: str
    source: Literal["local", "canonical-ready", "alias"] = "local"


class QueryExplanation(BaseModel):
    why_these_entities: List[str] = Field(default_factory=list)
    why_this_evidence: List[str] = Field(default_factory=list)
    reasoning_path: List[str] = Field(default_factory=list)
    selected_sections: List[str] = Field(default_factory=list)
    selection_signals: List[str] = Field(default_factory=list)


class EvidenceClusterItem(BaseModel):
    cluster_key: str
    entity: str
    relation_type: str
    evidences: List[SemanticEvidenceItem] = Field(default_factory=list)
    canonical_frequency: int = 0
    citation_count: int = 0
    importance: float = Field(default=0.0, ge=0.0, le=1.0)


class InsightItem(BaseModel):
    type: Literal["COMMON_PATTERN", "FREQUENT_RELATION", "CROSS_DOCUMENT_TREND"]
    text: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_clusters: List[str] = Field(default_factory=list)


class SemanticQueryAnswer(BaseModel):
    answer: str
    query_intent: str = "SUMMARY"
    matched_entities: List[MatchedEntityItem] = Field(default_factory=list)
    evidence: List[SemanticEvidenceItem] = Field(default_factory=list)
    related_nodes: List[RelatedNodeItem] = Field(default_factory=list)
    citations: List[CitationItem] = Field(default_factory=list)
    explanation: QueryExplanation = Field(default_factory=QueryExplanation)
    key_points: List[str] = Field(default_factory=list)
    insights: List[InsightItem] = Field(default_factory=list)
    clusters: List[EvidenceClusterItem] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limited_evidence: bool = False
    uncertainty_signal: bool = False
    uncertainty_reason: Optional[str] = None
    mode: Literal["semantic_grounded"] = "semantic_grounded"
