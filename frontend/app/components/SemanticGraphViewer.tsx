"use client";

import { useEffect, useMemo, useRef, useState, type ComponentProps, type MutableRefObject } from "react";
import ForceGraph3D from "react-force-graph-3d";
import { fetchSemanticGraph, toRenderData, toUserMessage } from "../lib/api";
import { GRAPH_LIMITS } from "../lib/constants";
import { resolveNodeDisplayName } from "../lib/documentLabel";
import type { GraphEdge, GraphMeta, GraphNode, GraphRenderData } from "../lib/types";
import { useAppStore } from "../store/useAppStore";

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
  const [graphMeta, setGraphMeta] = useState<GraphMeta>({ counts: {}, filters_applied: {} });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const graphFilters = useAppStore((state) => state.graphFilters);
  const graphRefreshToken = useAppStore((state) => state.graphRefreshToken);
  const selectedDocumentId = useAppStore((state) => state.selectedDocumentId);
  const graphFocusRelevantOnly = useAppStore((state) => state.graphFocusRelevantOnly);
  const setSelectedDocumentId = useAppStore((state) => state.setSelectedDocumentId);
  const requestGraphRefresh = useAppStore((state) => state.requestGraphRefresh);
  const highlightedNodeIds = useAppStore((state) => state.highlightedNodeIds);
  const selectedNodeId = useAppStore((state) => state.selectedNodeId);
  const primaryFocusNodeId = useAppStore((state) => state.primaryFocusNodeId);
  const secondaryFocusNodeIds = useAppStore((state) => state.secondaryFocusNodeIds);
  const setSelectedNode = useAppStore((state) => state.setSelectedNode);
  const setSelectedNodeContext = useAppStore((state) => state.setSelectedNodeContext);

  const [debouncedFilterKey, setDebouncedFilterKey] = useState<string>("");

  const hasDocumentFilter = Boolean(graphFilters.document_id);

  useEffect(() => {
    const nextKey = JSON.stringify({
      graphFilters,
      graphRefreshToken,
      selectedDocumentId,
    });
    const timer = setTimeout(() => setDebouncedFilterKey(nextKey), GRAPH_LIMITS.UPDATE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [graphFilters, graphRefreshToken, selectedDocumentId]);

  useEffect(() => {
    if (!debouncedFilterKey) return;
    let cancelled = false;

    const loadGraph = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetchSemanticGraph(graphFilters, {
          traceLabel: "viewer",
          forceRefresh: graphRefreshToken > 0,
        });
        if (!cancelled) {
          let effectiveResponse = response;
          let rendered = toRenderData(effectiveResponse);

          // If semantic mode is empty on initial/global scope, retry once with evidence enabled.
          // This prevents "blank until mode change" behavior when datasets are evidence-heavy.
          if (rendered.nodes.length === 0 && !graphFilters.document_id) {
            const fallbackFilters = {
              ...graphFilters,
              include_structural: true,
              include_evidence: true,
            };
            effectiveResponse = await fetchSemanticGraph(fallbackFilters, {
              traceLabel: "viewer-fallback",
              forceRefresh: graphRefreshToken > 0,
            });
            rendered = toRenderData(effectiveResponse);
          }

          setGraphData(rendered);
          setGraphMeta(effectiveResponse.meta || { counts: {}, filters_applied: {} });
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
  }, [debouncedFilterKey, graphFilters, selectedDocumentId, hasDocumentFilter, graphRefreshToken]);

  useEffect(() => {
    if (!graphRef.current) return;
    const priorityTargets = [primaryFocusNodeId, ...secondaryFocusNodeIds].filter((id): id is string => Boolean(id));
    if (priorityTargets.length === 0) return;
    const targetNode = graphData.nodes.find((node) => priorityTargets.includes(node.id));
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
  }, [primaryFocusNodeId, secondaryFocusNodeIds, graphData]);

  const degreeByNode = useMemo(() => {
    const degreeMap = new Map<string, number>();
    for (const link of graphData.links) {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      degreeMap.set(source, (degreeMap.get(source) || 0) + 1);
      degreeMap.set(target, (degreeMap.get(target) || 0) + 1);
    }
    return degreeMap;
  }, [graphData.links]);

  const nodeVal = useMemo(() => {
    return (node: GraphNode) => {
      const degree = degreeByNode.get(node.id) || 0;
      const properties = node.properties || {};
      const importance = asNumber(properties.importance) ?? asNumber(properties.confidence) ?? 0;
      return 5 + Math.min(8, degree * 0.55 + importance * 3);
    };
  }, [degreeByNode]);

  const focusedGraphState = useMemo(() => {
    const structuralFilteredNodes = graphData.nodes;
    const nodeIdSet = new Set(structuralFilteredNodes.map((node) => node.id));
    const structuralFilteredLinks = graphData.links.filter((link) => {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      return nodeIdSet.has(source) && nodeIdSet.has(target);
    });
    if (!graphFocusRelevantOnly || highlightedNodeIds.length === 0) {
      return { nodes: structuralFilteredNodes, links: structuralFilteredLinks, fallbackApplied: false };
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
    if (focusedNodes.length === 0 || focusedLinks.length === 0) {
      return { nodes: structuralFilteredNodes, links: structuralFilteredLinks, fallbackApplied: true };
    }
    return { nodes: focusedNodes, links: focusedLinks, fallbackApplied: false };
  }, [graphData, graphFocusRelevantOnly, highlightedNodeIds]);

  const boundedGraphData = useMemo(() => {
    const nodeById = new Map(focusedGraphState.nodes.map((node) => [node.id, node]));
    const degree = new Map<string, number>();
    for (const link of focusedGraphState.links) {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      degree.set(source, (degree.get(source) || 0) + 1);
      degree.set(target, (degree.get(target) || 0) + 1);
    }

    const priorityNodes = [...nodeById.values()].sort((a, b) => {
      const aPriority = highlightedNodeIds.includes(a.id) ? 1 : 0;
      const bPriority = highlightedNodeIds.includes(b.id) ? 1 : 0;
      if (aPriority !== bPriority) return bPriority - aPriority;
      return (degree.get(b.id) || 0) - (degree.get(a.id) || 0);
    });
    const keptNodes = priorityNodes.slice(0, GRAPH_LIMITS.MAX_NODES);
    const keptNodeIds = new Set(keptNodes.map((node) => node.id));
    const keptLinks = focusedGraphState.links
      .filter((link) => {
        const source = typeof link.source === "string" ? link.source : link.source.id;
        const target = typeof link.target === "string" ? link.target : link.target.id;
        return keptNodeIds.has(source) && keptNodeIds.has(target);
      })
      .slice(0, GRAPH_LIMITS.MAX_EDGES)
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
  }, [focusedGraphState, highlightedNodeIds]);

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
  }, [graphData.links]);

  useEffect(() => {
    if (!graphRef.current) return;
    graphRef.current.d3AlphaDecay?.(0.045);
    graphRef.current.d3VelocityDecay?.(0.38);
  }, []);

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
    setSelectedNode(node.id);
    setSelectedNodeContext({
      id: node.id,
      label: node.label,
      title: nodeTitle,
      shortDescription,
      documentName: docName,
      page,
      rawText: asString(properties.text) || asString(properties.surface_text),
      details: {
        summary: asString(properties.summary) || asString(properties.description),
        citation_label: asString(properties.citation_label),
      },
    });
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
              Show all documents
            </button>
          </div>
        </div>
      </div>
    );
  }

  const graphModeLabel = "Semantic Graph";
  const graphStateLabel = !selectedDocumentId
    ? "No document loaded"
    : `Filtered by document ${selectedDocumentId}`;
  const isGraphEmpty = boundedGraphData.nodes.length === 0;
  const totalNodes = graphMeta.counts.nodes || graphData.nodes.length;
  const filteredNodes = graphMeta.counts.in_scope_nodes || boundedGraphData.nodes.length;

  return (
    <div className="w-screen h-screen fixed inset-0 z-0 bg-black">
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 w-[min(980px,95vw)] border border-white/15 bg-black/70 rounded-xl px-4 py-2 font-mono">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] text-cyan-200">{graphModeLabel}</p>
            <p className="text-[10px] text-white/70">{graphStateLabel}</p>
            <p className="text-[10px] text-white/60">Showing {filteredNodes} / {totalNodes} nodes</p>
            <p className="text-[10px] text-white/50">Filtered semantic view</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-white/70">Nodes: {boundedGraphData.nodes.length}</p>
            <p className="text-[10px] text-white/70">Edges: {boundedGraphData.links.length}</p>
          </div>
        </div>
        {hasDocumentFilter && (
          <div className="mt-2 flex items-center gap-4 text-[10px] text-white/80">
            <button
              className="px-2 py-1 rounded border border-amber-400/50 text-amber-200 hover:bg-amber-500/10"
              onClick={() => setSelectedDocumentId(null)}
            >
              Clear filter
            </button>
          </div>
        )}
        {focusedGraphState.fallbackApplied && (
          <p className="mt-2 text-[10px] text-amber-200">
            Relevant focus not found in current scope. Showing full scoped graph.
          </p>
        )}
      </div>

      {isGraphEmpty && !isLoading && (
        <div className="absolute top-24 left-1/2 -translate-x-1/2 z-10 w-[min(760px,92vw)] border border-white/20 bg-black/80 rounded-xl p-4 text-white font-mono">
          <p className="text-xs uppercase tracking-wide text-amber-200">
            {selectedDocumentId ? "No graph for active filter" : "Graph loaded but empty"}
          </p>
          <p className="text-[11px] text-white/70 mt-2">
            {selectedDocumentId
              ? "No nodes matched the selected document scope. Clear the filter or switch to show all documents."
              : "The graph endpoint returned successfully, but there are no nodes to render yet."}
          </p>
          <div className="flex items-center gap-2 mt-3">
            {selectedDocumentId && (
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
          </div>
        </div>
      )}

      <ForceGraph3D
        // @ts-expect-error - upstream ref generics are broader than local graph node typing
        ref={forceGraphRef}
        graphData={boundedGraphData}
        backgroundColor="#000000"
        nodeColor={(node: GraphNode) => {
          if (selectedNodeId === node.id || primaryFocusNodeId === node.id) return "#f8fafc";
          if (secondaryFocusNodeIds.includes(node.id)) return "#cbd5e1";
          if (hoveredNodeId === node.id) return "#e2e8f0";
          const properties = node.properties || {};
          const confidence = asNumber(properties.confidence) ?? asNumber(properties.importance) ?? 0;
          const highlighted = highlightedNodeIds.includes(node.id) ? 0.22 : 0;
          const neighborBoost = selectedNodeId && neighborsByNode.get(selectedNodeId)?.has(node.id) ? 0.12 : 0;
          const relevance = Math.max(0.14, Math.min(0.9, 0.22 + confidence * 0.5 + highlighted + neighborBoost));
          return `rgba(148, 163, 184, ${relevance.toFixed(2)})`;
        }}
        nodeVal={nodeVal}
        nodeLabel={(node: GraphNode) => {
          const isFocusNode =
            node.id === selectedNodeId ||
            node.id === primaryFocusNodeId ||
            hoveredNodeId === node.id;
          if (!isFocusNode) {
            return "";
          }
          const properties = node.properties || {};
          const docName =
            asString(properties.file_name) ||
            asString(properties.document_name) ||
            asString(properties.document_title);
          const page =
            asNumber(properties.page) ??
            asNumber(properties.page_number) ??
            asNumber(properties.source_page);
          const sourceHint = docName ? `${docName}${typeof page === "number" ? ` · p.${page}` : ""}` : "";
          return sourceHint
            ? `${resolveNodeDisplayName(node)} (${node.label})\n${sourceHint}`
            : `${resolveNodeDisplayName(node)} (${node.label})`;
        }}
        linkColor={(link: GraphEdge) =>
          link.properties?.edge_scope === "bridged" ? "rgba(251, 191, 36, 0.35)" : "rgba(148, 163, 184, 0.35)"
        }
        linkWidth={(link: GraphEdge) => {
          const source = typeof link.source === "string" ? link.source : link.source.id;
          const target = typeof link.target === "string" ? link.target : link.target.id;
          if (source === primaryFocusNodeId || target === primaryFocusNodeId) return 1.6;
          if (source === selectedNodeId || target === selectedNodeId) return 1.3;
          if (link.properties?.edge_scope === "bridged") return 0.45;
          return 0.8;
        }}
        linkDirectionalParticles={0}
        onNodeClick={handleNodeClick}
        onNodeHover={(node) => setHoveredNodeId(node ? node.id : null)}
      />
    </div>
  );
}
