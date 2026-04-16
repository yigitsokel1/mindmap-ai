/**
 * Shared frontend contracts for semantic graph UI.
 */

export type GraphPreset = "semantic" | "evidence" | "citation";

export type SemanticNodeType =
  | "Document"
  | "Section"
  | "Passage"
  | "ReferenceEntry"
  | "InlineCitation"
  | "Author"
  | "Institution"
  | "Concept"
  | "Method"
  | "Dataset"
  | "Metric"
  | "Task"
  | "Evidence"
  | "RelationInstance";

export interface GraphNode {
  id: string;
  label: SemanticNodeType | string;
  type: string;
  display_name: string;
  name?: string;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
  z?: number;
}

export interface GraphEdge {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphMeta {
  counts: Record<string, number>;
  filters_applied: Record<string, unknown>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: GraphMeta;
}

// ForceGraph expects `links`, so we keep this render-level shape.
export interface GraphRenderData {
  nodes: GraphNode[];
  links: GraphEdge[];
}

// Legacy compatibility types (inactive path).
export type GraphLink = GraphEdge;
export type GraphData = GraphRenderData;

export interface GraphFilters {
  document_id?: string;
  node_types?: string[];
  include_structural?: boolean;
  include_evidence?: boolean;
  include_citations?: boolean;
}

export interface Document {
  id: string;
  name: string;
  label?: string;
  created_at?: string;
}

export interface NodeContext {
  id: string;
  label: string;
  title: string;
  documentName?: string;
  page?: number;
  rawText?: string;
  details?: NodeDetail | Record<string, unknown>;
}

export interface NodeRelationItem {
  id: string;
  type: string;
  name: string;
}

export interface NodeEvidenceItem {
  text: string;
  passage_id: string;
  document_id: string;
  section?: string | null;
  score?: number | null;
}

export interface NodeCitationItem {
  title: string;
  year?: number | null;
  label?: string | null;
}

export interface NodeRelationGroup {
  relation_type: string;
  count: number;
  items: NodeRelationItem[];
}

export interface NodeDetail {
  id: string;
  type: string;
  name: string;
  summary: string;
  relations: {
    incoming: NodeRelationItem[];
    outgoing: NodeRelationItem[];
  };
  grouped_relations: {
    incoming: NodeRelationGroup[];
    outgoing: NodeRelationGroup[];
  };
  evidences: NodeEvidenceItem[];
  citations: NodeCitationItem[];
  linked_canonical_entity?: Record<string, unknown> | null;
  canonical_aliases?: string[];
  appears_in_documents?: number;
  top_related_documents?: string[];
}

export interface SemanticEvidenceItem {
  relation_type: string;
  page?: number | null;
  snippet: string;
  section?: string | null;
  confidence?: number;
  related_node_ids: string[];
  document_id?: string | null;
  document_name?: string | null;
  citation_label?: string | null;
  reference_entry_id?: string | null;
}

export interface SemanticCitationItem {
  label: string;
  reference_entry_id?: string | null;
  page?: number | null;
  document_name?: string | null;
}

export interface SemanticRelatedNode {
  id: string;
  type: string;
  display_name: string;
}

export interface SemanticExplanation {
  why_these_entities: string[];
  why_this_evidence: string[];
  reasoning_path: string[];
  selected_sections: string[];
  selection_signals: string[];
}

export interface SemanticQueryResponse {
  answer: string;
  query_intent: string;
  matched_entities: SemanticRelatedNode[];
  evidence: SemanticEvidenceItem[];
  related_nodes: SemanticRelatedNode[];
  citations: SemanticCitationItem[];
  explanation: SemanticExplanation;
  confidence: number;
  limited_evidence?: boolean;
  uncertainty_signal?: boolean;
  uncertainty_reason?: string | null;
  mode: "semantic_grounded";
}

export interface IngestJobStatus {
  ingest_job_id: string;
  file_name: string;
  mode: string;
  stage:
    | "uploaded"
    | "parsing"
    | "detecting_sections"
    | "parsing_references"
    | "extracting_semantics"
    | "writing_graph"
    | "completed"
    | "failed";
  status: "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  document_id?: string | null;
  error?: string | null;
  details?: Record<string, unknown>;
}
