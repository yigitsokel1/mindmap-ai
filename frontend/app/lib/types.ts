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
  created_at?: string;
}

export interface NodeContext {
  id: string;
  label: string;
  title: string;
  documentName?: string;
  page?: number;
  rawText?: string;
  details?: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

export interface ChatSource {
  doc_name: string;
  page: number;
  score?: number;
}

export interface ChatResponse {
  result: string;
  sources?: ChatSource[];
  related_node_ids?: string[];
}

export type QueryMode = "legacy_chat" | "semantic_query";

export interface SemanticEvidenceItem {
  relation_type: string;
  page?: number | null;
  snippet: string;
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

export interface SemanticQueryResponse {
  answer: string;
  evidence: SemanticEvidenceItem[];
  related_nodes: SemanticRelatedNode[];
  citations: SemanticCitationItem[];
  confidence: number;
  mode: "semantic_grounded";
}
