import { API_ENDPOINTS, PRESET_FILTERS } from "./constants";
import type { GraphFilters, GraphPreset, GraphRenderData, GraphResponse } from "./types";

const DEFAULT_GRAPH_PRESET: GraphPreset = "semantic";

function buildGraphUrl(filters: GraphFilters): string {
  const url = new URL(API_ENDPOINTS.GRAPH_SEMANTIC);
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

function normalizeNodeTypes(nodeTypes?: string[]): string[] | undefined {
  if (!nodeTypes || nodeTypes.length === 0) return undefined;
  return [...nodeTypes].sort((a, b) => a.localeCompare(b));
}

export function stableGraphFilterKey(filters: GraphFilters): string {
  return JSON.stringify({
    document_id: filters.document_id ?? null,
    node_types: normalizeNodeTypes(filters.node_types) ?? [],
    include_structural: typeof filters.include_structural === "boolean" ? filters.include_structural : null,
    include_evidence: typeof filters.include_evidence === "boolean" ? filters.include_evidence : null,
    include_citations: typeof filters.include_citations === "boolean" ? filters.include_citations : null,
  });
}

const inFlightGraphRequests = new Map<string, Promise<GraphResponse>>();
const graphResponseCache = new Map<string, { expiresAt: number; data: GraphResponse }>();
const GRAPH_RESPONSE_TTL_MS = 5000;

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
  const key = stableGraphFilterKey(filters);
  const now = Date.now();
  const cached = graphResponseCache.get(key);
  if (cached && cached.expiresAt > now) {
    return cached.data;
  }

  const active = inFlightGraphRequests.get(key);
  if (active) {
    return active;
  }

  const request = (async () => {
    const response = await fetch(buildGraphUrl(filters));
    if (!response.ok) {
      throw new Error(`Failed to fetch semantic graph: ${response.statusText}`);
    }
    const data = (await response.json()) as GraphResponse;
    graphResponseCache.set(key, { data, expiresAt: Date.now() + GRAPH_RESPONSE_TTL_MS });
    return data;
  })();

  inFlightGraphRequests.set(key, request);
  try {
    return await request;
  } finally {
    inFlightGraphRequests.delete(key);
  }
}

export function toRenderData(response: GraphResponse): GraphRenderData {
  return {
    nodes: response.nodes || [],
    links: response.edges || [],
  };
}
