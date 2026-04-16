/**
 * Application-wide constants
 */

import type { GraphFilters, GraphPreset, SemanticNodeType } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export const API_ENDPOINTS = {
  GRAPH_SEMANTIC: apiUrl("/api/graph/semantic"),
  GRAPH_NODE_DETAIL: (nodeId: string, documentId?: string) =>
    `${apiUrl(`/api/graph/node/${encodeURIComponent(nodeId)}`)}${
      documentId ? `?document_id=${encodeURIComponent(documentId)}` : ""
    }`,
  QUERY_SEMANTIC: apiUrl("/api/query/semantic"),
  INGEST: apiUrl("/api/ingest"),
  INGEST_STATUS: (jobId: string) => apiUrl(`/api/ingest/${encodeURIComponent(jobId)}`),
  DOCUMENTS: apiUrl("/api/documents"),
  STATIC: (filename: string) => apiUrl(`/static/${encodeURIComponent(filename)}`),
} as const;

export const PRESET_FILTERS: Record<GraphPreset, GraphFilters> = {
  semantic: {
    include_structural: true,
    include_evidence: false,
    include_citations: false,
  },
  evidence: {
    include_structural: true,
    include_evidence: true,
    include_citations: false,
  },
  citation: {
    include_structural: true,
    include_evidence: true,
    include_citations: true,
  },
};

export const PRESET_LABELS: Record<GraphPreset, string> = {
  semantic: "Semantic",
  evidence: "Evidence",
  citation: "Citation",
};

export const CORE_SEMANTIC_NODE_TYPES: SemanticNodeType[] = [
  "Author",
  "Institution",
  "Concept",
  "Method",
  "Dataset",
  "Metric",
  "Task",
  "RelationInstance",
];
