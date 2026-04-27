import { API_ENDPOINTS, DEFAULT_SEMANTIC_FILTERS } from "./constants";
import type { GraphFilters, GraphRenderData, GraphResponse } from "./types";

function buildGraphUrl(filters: GraphFilters): string {
  const base =
    typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:3000";
  const url = new URL(API_ENDPOINTS.GRAPH_SEMANTIC, base);
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

function withoutDocumentFilter(filters: GraphFilters): GraphFilters {
  const { document_id: _ignored, ...rest } = filters;
  return rest;
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

export interface FetchSemanticGraphOptions {
  bypassDocumentFilter?: boolean;
  traceLabel?: string;
  forceRefresh?: boolean;
}

const inFlightGraphRequests = new Map<string, Promise<GraphResponse>>();
const graphResponseCache = new Map<string, { expiresAt: number; data: GraphResponse }>();
const GRAPH_RESPONSE_TTL_MS = 5000;
const DEFAULT_TIMEOUT_MS = 12000;

export type AppErrorType = "network" | "timeout" | "server" | "not_found" | "validation" | "partial_data" | "unknown";

export class AppError extends Error {
  readonly type: AppErrorType;
  readonly status?: number;

  constructor(message: string, type: AppErrorType, status?: number) {
    super(message);
    this.type = type;
    this.status = status;
  }
}

function classifyStatus(status: number): AppErrorType {
  if (status === 404) return "not_found";
  if (status === 422 || status === 400) return "validation";
  if (status === 206) return "partial_data";
  if (status >= 500) return "server";
  return "unknown";
}

export function toUserMessage(error: unknown): string {
  if (error instanceof AppError) {
    if (error.type === "network") return "Network issue. Check your connection and try again.";
    if (error.type === "timeout") return "Request timed out. Please retry.";
    if (error.type === "server") return "Backend is currently unavailable. Please try again shortly.";
    if (error.type === "not_found") return "Requested data was not found.";
    if (error.type === "validation") return "Request could not be processed. Please review your input.";
    if (error.type === "partial_data") return "Partial data returned. Some details may be missing.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Unexpected error occurred.";
}

export async function fetchJson<T>(url: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        // keep fallback detail
      }
      throw new AppError(detail || "Request failed", classifyStatus(response.status), response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof AppError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new AppError("Request timed out", "timeout");
    }
    throw new AppError("Network request failed", "network");
  } finally {
    clearTimeout(timeout);
  }
}

export function getSemanticFilters(overrides?: GraphFilters): GraphFilters {
  return {
    ...DEFAULT_SEMANTIC_FILTERS,
    ...overrides,
  };
}

export async function fetchSemanticGraph(
  filters: GraphFilters = {},
  options: FetchSemanticGraphOptions = {}
): Promise<GraphResponse> {
  const effectiveFilters = options.bypassDocumentFilter ? withoutDocumentFilter(filters) : filters;
  const key = stableGraphFilterKey(effectiveFilters);
  const now = Date.now();
  const cached = options.forceRefresh ? undefined : graphResponseCache.get(key);
  if (cached && cached.expiresAt > now) {
    if (options.traceLabel) {
      console.debug(`[graph-trace:${options.traceLabel}] cache-hit`, {
        filters: effectiveFilters,
        nodeCount: cached.data.nodes?.length ?? 0,
        edgeCount: cached.data.edges?.length ?? 0,
      });
    }
    return cached.data;
  }

  const active = options.forceRefresh ? undefined : inFlightGraphRequests.get(key);
  if (active) {
    return active;
  }

  const request = (async () => {
    const url = buildGraphUrl(effectiveFilters);
    if (options.traceLabel) {
      console.debug(`[graph-trace:${options.traceLabel}] fetch-start`, {
        url,
        filters: effectiveFilters,
      });
    }
    const data = await fetchJson<GraphResponse>(url, undefined, DEFAULT_TIMEOUT_MS);
    if (options.traceLabel) {
      console.debug(`[graph-trace:${options.traceLabel}] fetch-success`, {
        filters: effectiveFilters,
        nodeCount: data.nodes?.length ?? 0,
        edgeCount: data.edges?.length ?? 0,
        metaCounts: data.meta?.counts ?? {},
        filtersApplied: data.meta?.filters_applied ?? {},
      });
    }
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
  const renderData = {
    nodes: response.nodes || [],
    links: response.edges || [],
  };
  console.debug("[graph-trace:transform] toRenderData", {
    nodeCount: renderData.nodes.length,
    edgeCount: renderData.links.length,
  });
  return renderData;
}
