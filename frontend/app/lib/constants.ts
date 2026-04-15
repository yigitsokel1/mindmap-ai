/**
 * Application-wide constants
 */

import type { GraphFilters, GraphPreset, SemanticNodeType } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  GRAPH: `${API_BASE_URL}/api/graph`,
  GRAPH_SEMANTIC: `${API_BASE_URL}/api/graph/semantic`,
  GRAPH_LEGACY: `${API_BASE_URL}/api/graph/legacy`,
  CHAT: `${API_BASE_URL}/api/chat`,
  QUERY_SEMANTIC: `${API_BASE_URL}/api/query/semantic`,
  INGEST: `${API_BASE_URL}/api/ingest`,
  DOCUMENTS: `${API_BASE_URL}/api/documents`,
  STATIC: (filename: string) => `${API_BASE_URL}/static/${encodeURIComponent(filename)}`,
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
