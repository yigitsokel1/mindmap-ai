/**
 * Application-wide constants
 */

import type { GraphFilters, SemanticNodeType } from "./types";

// Default to backend directly in local dev so long-running ingest requests
// do not fail via the Next.js dev proxy timeout/socket reset path.
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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
  STATIC: (filename: string) => apiUrl(`/static/${encodeURIComponent(filename)}`),
} as const;

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

export const DEFAULT_SEMANTIC_FILTERS: GraphFilters = {
  include_structural: false,
  include_evidence: false,
  include_citations: false,
  node_types: [...CORE_SEMANTIC_NODE_TYPES],
};

export const GRAPH_LIMITS = {
  MAX_NODES: 300,
  MAX_EDGES: 500,
  INITIAL_NODES: 120,
  INITIAL_EDGES: 180,
  UPDATE_DEBOUNCE_MS: 300,
} as const;

