import { API_ENDPOINTS, PRESET_FILTERS } from "./constants";
import type { GraphFilters, GraphPreset, GraphRenderData, GraphResponse } from "./types";

const DEFAULT_GRAPH_PRESET: GraphPreset = "semantic";

function buildGraphUrl(filters: GraphFilters): string {
  const url = new URL(API_ENDPOINTS.GRAPH);
  const params = url.searchParams;

  if (filters.document_id) {
    params.set("document_id", filters.document_id);
  }

  if (filters.node_types && filters.node_types.length > 0) {
    for (const nodeType of filters.node_types) {
      params.append("node_types", nodeType);
    }
  }

  if (typeof filters.include_structural === "boolean") {
    params.set("include_structural", String(filters.include_structural));
  }
  if (typeof filters.include_evidence === "boolean") {
    params.set("include_evidence", String(filters.include_evidence));
  }
  if (typeof filters.include_citations === "boolean") {
    params.set("include_citations", String(filters.include_citations));
  }

  return url.toString();
}

export function getPresetFilters(
  preset: GraphPreset = DEFAULT_GRAPH_PRESET,
  overrides?: GraphFilters
): GraphFilters {
  return {
    ...PRESET_FILTERS[preset],
    ...overrides,
  };
}

export async function fetchSemanticGraph(filters: GraphFilters = {}): Promise<GraphResponse> {
  const response = await fetch(buildGraphUrl(filters));
  if (!response.ok) {
    throw new Error(`Failed to fetch semantic graph: ${response.statusText}`);
  }

  return response.json() as Promise<GraphResponse>;
}

export function toRenderData(response: GraphResponse): GraphRenderData {
  return {
    nodes: response.nodes || [],
    links: response.edges || [],
  };
}
