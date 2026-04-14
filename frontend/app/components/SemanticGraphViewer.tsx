"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph3D from "react-force-graph-3d";
import { fetchSemanticGraph, toRenderData } from "../lib/api";
import type { GraphNode, GraphRenderData } from "../lib/types";
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

export default function SemanticGraphViewer() {
  const graphRef = useRef<any>(null);
  const [graphData, setGraphData] = useState<GraphRenderData>({ nodes: [], links: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const {
    graphFilters,
    highlightedNodeIds,
    setSelectedNode,
    setSelectedNodeContext,
    openPDFViewer,
  } = useAppStore();

  useEffect(() => {
    const loadGraph = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetchSemanticGraph(graphFilters);
        setGraphData(toRenderData(response));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Graph load failed");
      } finally {
        setIsLoading(false);
      }
    };

    loadGraph();
  }, [graphFilters]);

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

  const handleNodeClick = (node: GraphNode) => {
    const properties = node.properties || {};
    const nodeTitle = node.display_name || node.id;
    const docName =
      asString(properties.file_name) ||
      asString(properties.document_name) ||
      asString(properties.document_title);
    const page =
      asNumber(properties.page) ??
      asNumber(properties.page_number) ??
      asNumber(properties.source_page);

    setSelectedNode(node.id);
    setSelectedNodeContext({
      id: node.id,
      label: node.label,
      title: nodeTitle,
      documentName: docName,
      page,
      rawText: asString(properties.text) || asString(properties.surface_text),
      details: properties,
    });

    // Minimum graph-to-document bridge requested in sprint scope.
    if (
      (node.label === "Passage" || node.label === "Evidence") &&
      docName &&
      typeof page === "number"
    ) {
      const pageNumber = page < 1 ? page + 1 : page;
      openPDFViewer(`/static/${encodeURIComponent(docName)}`, docName, pageNumber);
    }
  };

  if (isLoading) {
    return <div className="w-screen h-screen fixed inset-0 z-0 bg-black" />;
  }

  if (error) {
    return (
      <div className="w-screen h-screen fixed inset-0 z-0 bg-black flex items-center justify-center text-red-300 text-sm font-mono">
        {error}
      </div>
    );
  }

  return (
    <div className="w-screen h-screen fixed inset-0 z-0 bg-black">
      <ForceGraph3D
        ref={graphRef}
        graphData={graphData}
        backgroundColor="#000000"
        nodeColor={(node: GraphNode) => NODE_COLORS[node.label] || "#94a3b8"}
        nodeVal={nodeVal}
        nodeLabel={(node: GraphNode) => `${node.display_name} [${node.label}]`}
        linkColor={() => "rgba(148, 163, 184, 0.35)"}
        linkWidth={0.8}
        linkDirectionalParticles={0}
        onNodeClick={handleNodeClick}
      />
    </div>
  );
}
