"use client";

import { useEffect, useMemo, useRef, useState, type ComponentProps, type MutableRefObject } from "react";
import ForceGraph3D from "react-force-graph-3d";
import { fetchSemanticGraph, toRenderData, toUserMessage } from "../lib/api";
import { CORE_SEMANTIC_NODE_TYPES, GRAPH_LIMITS } from "../lib/constants";
import { resolveNodeDisplayName } from "../lib/documentLabel";
import type { GraphEdge, GraphNode, GraphRenderData } from "../lib/types";
import { useAppStore } from "../store/useAppStore";

const NODE_COLORS: Record<string, string> = {
  Document: "#f59e0b",
  Section: "#94a3b8",
  Passage: "#22c55e",
  ReferenceEntry: "#f97316",
  InlineCitation: "#facc15",
  Author: "#eab308",
  Institution: "#06b6d4",
  Concept: "#22d3ee",
  Method: "#a78bfa",
  Dataset: "#14b8a6",
  Metric: "#f472b6",
  Task: "#60a5fa",
  Evidence: "#fb7185",
  RelationInstance: "#c084fc",
};

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

type CameraPosition = { x: number; y: number; z: number };

interface GraphViewerHandle {
  cameraPosition: (
    position: CameraPosition,
    lookAt?: CameraPosition,
    ms?: number
  ) => void;
  d3ReheatSimulation?: () => void;
  d3AlphaDecay?: (value: number) => void;
  d3VelocityDecay?: (value: number) => void;
}

export default function SemanticGraphViewer() {
  const forceGraphRef = useRef<unknown>(undefined) as NonNullable<ComponentProps<typeof ForceGraph3D>["ref"]>;
  const graphRef = forceGraphRef as unknown as MutableRefObject<GraphViewerHandle | null>;
  const [graphData, setGraphData] = useState<GraphRenderData>({ nodes: [], links: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const graphFilters = useAppStore((state) => state.graphFilters);
  const graphRefreshToken = useAppStore((state) => state.graphRefreshToken);
  const selectedDocumentId = useAppStore((state) => state.selectedDocumentId);
  const graphDebugEnabled = useAppStore((state) => state.graphDebugEnabled);
  const graphBypassDocumentFilter = useAppStore((state) => state.graphBypassDocumentFilter);
  const graphFocusRelevantOnly = useAppStore((state) => state.graphFocusRelevantOnly);
  const queryMode = useAppStore((state) => state.queryMode);
  const setSelectedDocumentId = useAppStore((state) => state.setSelectedDocumentId);
  const requestGraphRefresh = useAppStore((state) => state.requestGraphRefresh);
  const highlightedNodeIds = useAppStore((state) => state.highlightedNodeIds);
  const setSelectedNode = useAppStore((state) => state.setSelectedNode);
  const setSelectedNodeContext = useAppStore((state) => state.setSelectedNodeContext);
  const openPDFViewer = useAppStore((state) => state.openPDFViewer);

  const [rawPayload, setRawPayload] = useState<unknown>(null);
  const [debouncedFilterKey, setDebouncedFilterKey] = useState<string>("");
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());

  const isDev = process.env.NODE_ENV !== "production";
  const hasDocumentFilter = Boolean(graphFilters.document_id);

  useEffect(() => {
    const nextKey = JSON.stringify({
      graphFilters,
      graphRefreshToken,
      graphBypassDocumentFilter,
      selectedDocumentId,
    });
    const timer = setTimeout(() => setDebouncedFilterKey(nextKey), GRAPH_LIMITS.UPDATE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [graphFilters, graphRefreshToken, graphBypassDocumentFilter, selectedDocumentId]);

  useEffect(() => {
    if (!debouncedFilterKey) return;
    let cancelled = false;

    const loadGraph = async () => {
      setIsLoading(true);
      setError(null);

      try {
        console.debug("[graph-trace:store-input]", {
          selectedDocumentId,
          graphFilters,
          graphMode: "semantic",
          graphBypassDocumentFilter,
        });
        const response = await fetchSemanticGraph(graphFilters, {
          bypassDocumentFilter: graphBypassDocumentFilter,
          traceLabel: "viewer",
        });
        if (!cancelled) {
          let effectiveResponse = response;
          let rendered = toRenderData(effectiveResponse);

          // If semantic mode is empty on initial/global scope, retry once with evidence enabled.
          // This prevents "blank until mode change" behavior when datasets are evidence-heavy.
          if (rendered.nodes.length === 0 && !graphFilters.document_id && !graphBypassDocumentFilter) {
            const fallbackFilters = {
              ...graphFilters,
              include_structural: true,
              include_evidence: true,
            };
            console.debug("[graph-trace:viewer] semantic-empty -> fallback-fetch", {
              fallbackFilters,
            });
            effectiveResponse = await fetchSemanticGraph(fallbackFilters, {
              bypassDocumentFilter: false,
              traceLabel: "viewer-fallback",
            });
            rendered = toRenderData(effectiveResponse);
          }

          setRawPayload(effectiveResponse);
          setGraphData(rendered);
          console.debug("[graph-trace:renderer-input]", {
            selectedDocumentId,
            graphMode: "semantic",
            hasDocumentFilter,
            bypassDocumentFilter: graphBypassDocumentFilter,
            renderedNodes: rendered.nodes.length,
            renderedEdges: rendered.links.length,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(toUserMessage(err));
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    loadGraph();
    return () => {
      cancelled = true;
    };
  }, [debouncedFilterKey, graphFilters, graphBypassDocumentFilter, selectedDocumentId, hasDocumentFilter]);

  useEffect(() => {
    setExpandedNodeIds(new Set(highlightedNodeIds));
  }, [highlightedNodeIds, graphRefreshToken]);

  useEffect(() => {
    if (!graphRef.current || highlightedNodeIds.length === 0) return;

    const targetNode = graphData.nodes.find((node) => highlightedNodeIds.includes(node.id));
    if (!targetNode) return;

    const distance = 130;
    const x = targetNode.x || 0;
    const y = targetNode.y || 0;
    const z = targetNode.z || 0;
    const distRatio = 1 + distance / Math.hypot(x, y, z || 1);

    graphRef.current.cameraPosition(
      { x: x * distRatio, y: y * distRatio, z: z * distRatio },
      { x, y, z },
      1200
    );
  }, [highlightedNodeIds, graphData]);

  const nodeVal = useMemo(() => {
    return (node: GraphNode) => {
      if (node.label === "Document") return 12;
      if (node.label === "Evidence" || node.label === "InlineCitation") return 4;
      return 7;
    };
  }, []);

  const filteredGraphData = useMemo(() => {
    const structuralFilteredNodes =
      queryMode === "answer"
        ? graphData.nodes.filter((node) => {
            if (node.label === "Section" || node.label === "Passage" || node.label === "InlineCitation" || node.label === "ReferenceEntry") return false;
            const name = String(node.display_name || "").toLowerCase();
            if (name.includes("acknowledgement") || name.includes("acknowledgment")) return false;
            if (node.label === "Section" && !name.trim()) return false;
            const evidenceCount = Number((node.properties?.evidence_count as number | undefined) ?? 0);
            if ((node.label === "Document" || node.label === "Section") && evidenceCount <= 0) return false;
            if (CORE_SEMANTIC_NODE_TYPES.includes(node.label as never)) return true;
            return queryMode === "explore";
          })
        : graphData.nodes;
    const nodeIdSet = new Set(structuralFilteredNodes.map((node) => node.id));
    const structuralFilteredLinks = graphData.links.filter((link) => {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      return nodeIdSet.has(source) && nodeIdSet.has(target);
    });
    if (!graphFocusRelevantOnly || highlightedNodeIds.length === 0) {
      return { nodes: structuralFilteredNodes, links: structuralFilteredLinks };
    }
    const highlighted = new Set(highlightedNodeIds);
    const focusedLinks = structuralFilteredLinks.filter((link) => {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      return highlighted.has(source) || highlighted.has(target);
    });
    const focusedNodeIds = new Set<string>(highlightedNodeIds);
    for (const link of focusedLinks) {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      focusedNodeIds.add(source);
      focusedNodeIds.add(target);
    }
    const focusedNodes = structuralFilteredNodes.filter((node) => focusedNodeIds.has(node.id));
    return { nodes: focusedNodes, links: focusedLinks };
  }, [graphData, graphFocusRelevantOnly, highlightedNodeIds, queryMode]);

  const boundedGraphData = useMemo(() => {
    const nodeById = new Map(filteredGraphData.nodes.map((node) => [node.id, node]));
    const degree = new Map<string, number>();
    for (const link of filteredGraphData.links) {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      degree.set(source, (degree.get(source) || 0) + 1);
      degree.set(target, (degree.get(target) || 0) + 1);
    }

    const priorityNodes = [...nodeById.values()].sort((a, b) => {
      const aPriority = highlightedNodeIds.includes(a.id) || expandedNodeIds.has(a.id) ? 1 : 0;
      const bPriority = highlightedNodeIds.includes(b.id) || expandedNodeIds.has(b.id) ? 1 : 0;
      if (aPriority !== bPriority) return bPriority - aPriority;
      return (degree.get(b.id) || 0) - (degree.get(a.id) || 0);
    });
    const lazyNodeLimit = expandedNodeIds.size > 0 ? GRAPH_LIMITS.MAX_NODES : GRAPH_LIMITS.INITIAL_NODES;
    const keptNodes = priorityNodes.slice(0, Math.min(lazyNodeLimit, GRAPH_LIMITS.MAX_NODES));
    const keptNodeIds = new Set(keptNodes.map((node) => node.id));
    const lazyEdgeLimit = expandedNodeIds.size > 0 ? GRAPH_LIMITS.MAX_EDGES : GRAPH_LIMITS.INITIAL_EDGES;
    const keptLinks = filteredGraphData.links
      .filter((link) => {
        const source = typeof link.source === "string" ? link.source : link.source.id;
        const target = typeof link.target === "string" ? link.target : link.target.id;
        return keptNodeIds.has(source) && keptNodeIds.has(target);
      })
      .slice(0, lazyEdgeLimit)
      .map((link): GraphEdge => {
        const source = typeof link.source === "string" ? link.source : link.source.id;
        const target = typeof link.target === "string" ? link.target : link.target.id;
        return {
          ...link,
          source,
          target,
        };
      });
    return { nodes: keptNodes, links: keptLinks };
  }, [expandedNodeIds, filteredGraphData, highlightedNodeIds]);

  const neighborsByNode = useMemo(() => {
    const byNode = new Map<string, Set<string>>();
    for (const link of boundedGraphData.links) {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      if (!byNode.has(source)) byNode.set(source, new Set());
      if (!byNode.has(target)) byNode.set(target, new Set());
      byNode.get(source)?.add(target);
      byNode.get(target)?.add(source);
    }
    return byNode;
  }, [boundedGraphData.links]);

  useEffect(() => {
    if (!graphRef.current) return;
    const frame = requestAnimationFrame(() => {
      try {
        graphRef.current?.d3ReheatSimulation?.();
      } catch {
        // Ignore force-engine transient errors during hot reload.
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [boundedGraphData]);

  const handleNodeClick = (node: GraphNode) => {
    const properties = node.properties || {};
    const nodeTitle = resolveNodeDisplayName(node);
    const docName =
      asString(properties.file_name) ||
      asString(properties.document_name) ||
      asString(properties.document_title);
    const page =
      asNumber(properties.page) ??
      asNumber(properties.page_number) ??
      asNumber(properties.source_page);

    const shortDescription =
      asString(properties.summary) ||
      asString(properties.description) ||
      `${node.label} node focused in semantic graph.`;
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      next.add(node.id);
      neighborsByNode.get(node.id)?.forEach((neighborId) => next.add(neighborId));
      return next;
    });
    setSelectedNode(node.id);
    setSelectedNodeContext({
      id: node.id,
      label: node.label,
      title: nodeTitle,
      shortDescription,
      documentName: docName,
      page,
      rawText: asString(properties.text) || asString(properties.surface_text),
      details: properties,
    });

    if ((node.label === "Passage" || node.label === "Evidence") && docName && typeof page === "number") {
      const pageNumber = page < 1 ? page + 1 : page;
      openPDFViewer(`/static/${encodeURIComponent(docName)}`, docName, pageNumber);
      return;
    }
    if ((node.label === "InlineCitation" || node.label === "ReferenceEntry") && docName) {
      openPDFViewer(`/static/${encodeURIComponent(docName)}`, docName, typeof page === "number" ? page : 1);
    }
  };

  if (isLoading) {
    return <div className="w-screen h-screen fixed inset-0 z-0 bg-black" />;
  }

  if (error) {
    return (
      <div className="w-screen h-screen fixed inset-0 z-0 bg-black">
        <div className="absolute top-6 left-1/2 -translate-x-1/2 w-[min(760px,92vw)] border border-red-500/40 bg-black/80 rounded-xl p-4 text-red-200 font-mono">
          <p className="text-xs uppercase tracking-wide">Graph fetch failed</p>
          <p className="text-xs mt-2">{error}</p>
          <div className="flex items-center gap-2 mt-3">
            <button
              className="px-3 py-1.5 rounded border border-white/20 text-white/90 text-[11px] hover:bg-white/10"
              onClick={() => requestGraphRefresh()}
            >
              Reload
            </button>
            <button
              className="px-3 py-1.5 rounded border border-white/20 text-white/90 text-[11px] hover:bg-white/10"
              onClick={() => setSelectedDocumentId(null)}
            >
              Show all
            </button>
          </div>
        </div>
      </div>
    );
  }

  const graphModeLabel = "Semantic Graph";
  const graphStateLabel = !selectedDocumentId
    ? "No document loaded"
    : graphBypassDocumentFilter
      ? `Showing all docs (filter bypass on; selected: ${selectedDocumentId})`
      : `Filtered by document ${selectedDocumentId}`;
  const isGraphEmpty = boundedGraphData.nodes.length === 0;

  return (
    <div className="w-screen h-screen fixed inset-0 z-0 bg-black">
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 w-[min(980px,95vw)] border border-white/15 bg-black/70 rounded-xl px-4 py-2 font-mono">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] text-cyan-200">{graphModeLabel}</p>
            <p className="text-[10px] text-white/70">{graphStateLabel}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-white/70">Nodes: {boundedGraphData.nodes.length}</p>
            <p className="text-[10px] text-white/70">Edges: {boundedGraphData.links.length}</p>
          </div>
        </div>
        {isDev && (
          <div className="mt-2 flex items-center gap-4 text-[10px] text-white/80">
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={graphBypassDocumentFilter}
                onChange={(event) => useAppStore.getState().setGraphBypassDocumentFilter(event.target.checked)}
              />
              Bypass document filter
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={graphDebugEnabled}
                onChange={(event) => useAppStore.getState().setGraphDebugEnabled(event.target.checked)}
              />
              Graph debug
            </label>
            {hasDocumentFilter && (
              <button
                className="px-2 py-1 rounded border border-amber-400/50 text-amber-200 hover:bg-amber-500/10"
                onClick={() => setSelectedDocumentId(null)}
              >
                Clear filter
              </button>
            )}
          </div>
        )}
      </div>

      {isGraphEmpty && !isLoading && (
        <div className="absolute top-24 left-1/2 -translate-x-1/2 z-10 w-[min(760px,92vw)] border border-white/20 bg-black/80 rounded-xl p-4 text-white font-mono">
          <p className="text-xs uppercase tracking-wide text-amber-200">
            {selectedDocumentId && !graphBypassDocumentFilter ? "No graph for active filter" : "Graph loaded but empty"}
          </p>
          <p className="text-[11px] text-white/70 mt-2">
            {selectedDocumentId && !graphBypassDocumentFilter
              ? "No nodes matched the selected document scope. Clear the filter or switch to show all documents."
              : "The graph endpoint returned successfully, but there are no nodes to render yet."}
          </p>
          <div className="flex items-center gap-2 mt-3">
            {selectedDocumentId && !graphBypassDocumentFilter && (
              <button
                className="px-3 py-1.5 rounded border border-white/20 text-[11px] hover:bg-white/10"
                onClick={() => setSelectedDocumentId(null)}
              >
                Clear filter
              </button>
            )}
            <button
              className="px-3 py-1.5 rounded border border-white/20 text-[11px] hover:bg-white/10"
              onClick={() => requestGraphRefresh()}
            >
              Reload
            </button>
            <button
              className="px-3 py-1.5 rounded border border-white/20 text-[11px] hover:bg-white/10"
              onClick={() => useAppStore.getState().setGraphBypassDocumentFilter(true)}
            >
              Show all
            </button>
          </div>
        </div>
      )}

      <ForceGraph3D
        // @ts-expect-error - upstream ref generics are broader than local graph node typing
        ref={forceGraphRef}
        graphData={boundedGraphData}
        backgroundColor="#000000"
        nodeColor={(node: GraphNode) => {
          const base = NODE_COLORS[node.label] || "#94a3b8";
          if (highlightedNodeIds.length === 0) return base;
          if (highlightedNodeIds.includes(node.id)) return "#f8fafc";
          const selected = useAppStore.getState().selectedNodeId;
          if (selected && neighborsByNode.get(selected)?.has(node.id)) return base;
          return "rgba(148, 163, 184, 0.18)";
        }}
        nodeVal={nodeVal}
        nodeLabel={(node: GraphNode) => `${resolveNodeDisplayName(node)} [${node.label}]`}
        linkColor={() => "rgba(148, 163, 184, 0.35)"}
        linkWidth={0.8}
        linkDirectionalParticles={0}
        onNodeClick={handleNodeClick}
      />
      {graphDebugEnabled && isDev && (
        <div className="absolute right-4 bottom-4 z-10 w-[min(460px,92vw)] border border-cyan-400/30 bg-black/85 rounded-lg p-3 text-[10px] font-mono text-cyan-100">
          <p className="uppercase tracking-wide text-cyan-300">Graph Debug</p>
          <p className="mt-1 text-white/80">
            nodeCount={boundedGraphData.nodes.length} edgeCount={boundedGraphData.links.length}
          </p>
          <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap wrap-break-word text-white/70">
            {JSON.stringify(rawPayload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
