import { create } from "zustand";
import { PRESET_FILTERS } from "../lib/constants";
import type { GraphFilters, GraphPreset, NodeContext, QueryMode } from "../lib/types";

function normalizeTypes(nodeTypes?: string[]): string[] {
  return nodeTypes ? [...nodeTypes].sort((a, b) => a.localeCompare(b)) : [];
}

function sameFilters(a: GraphFilters, b: GraphFilters): boolean {
  return (
    (a.document_id || undefined) === (b.document_id || undefined) &&
    a.include_structural === b.include_structural &&
    a.include_evidence === b.include_evidence &&
    a.include_citations === b.include_citations &&
    JSON.stringify(normalizeTypes(a.node_types)) === JSON.stringify(normalizeTypes(b.node_types))
  );
}

interface AppState {
  // UI State
  isCommandCenterOpen: boolean;
  activeTab: "chat" | "files";
  queryMode: QueryMode;
  isPDFViewerOpen: boolean;
  selectedNodeId: string | null;
  
  // PDF Viewer State
  pdfUrl: string | null;
  pdfDocName: string | null;
  pdfPage: number | null;
  
  // Graph State
  highlightedNodeIds: string[];
  isGraphFocused: boolean; // For blur/dim effect when panels are open
  graphPreset: GraphPreset;
  selectedDocumentId: string | null;
  graphFilters: GraphFilters;
  graphRefreshToken: number;
  selectedNodeContext: NodeContext | null;
  
  // Actions
  toggleCommandCenter: () => void;
  setActiveTab: (tab: "chat" | "files") => void;
  setQueryMode: (mode: QueryMode) => void;
  openPDFViewer: (url: string, docName: string, page: number) => void;
  closePDFViewer: () => void;
  setSelectedNode: (nodeId: string | null) => void;
  setHighlightedNodes: (nodeIds: string[]) => void;
  setGraphFocused: (focused: boolean) => void;
  setGraphPreset: (preset: GraphPreset) => void;
  setSelectedDocumentId: (documentId: string | null) => void;
  updateGraphFilters: (filters: Partial<GraphFilters>) => void;
  requestGraphRefresh: () => void;
  setSelectedNodeContext: (context: NodeContext | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial State
  isCommandCenterOpen: true,
  activeTab: "chat",
  queryMode: "legacy_chat",
  isPDFViewerOpen: false,
  selectedNodeId: null,
  pdfUrl: null,
  pdfDocName: null,
  pdfPage: null,
  highlightedNodeIds: [],
  isGraphFocused: true,
  graphPreset: "semantic",
  selectedDocumentId: null,
  graphFilters: { ...PRESET_FILTERS.semantic },
  graphRefreshToken: 0,
  selectedNodeContext: null,
  
  // Actions
  toggleCommandCenter: () => set((state) => ({ isCommandCenterOpen: !state.isCommandCenterOpen })),
  setActiveTab: (tab: "chat" | "files") => set({ activeTab: tab }),
  setQueryMode: (mode: QueryMode) => set({ queryMode: mode }),
  openPDFViewer: (url: string, docName: string, page: number) =>
    set({
      isPDFViewerOpen: true,
      pdfUrl: url,
      pdfDocName: docName,
      pdfPage: page,
      isGraphFocused: false,
    }),
  closePDFViewer: () =>
    set({
      isPDFViewerOpen: false,
      pdfUrl: null,
      pdfDocName: null,
      pdfPage: null,
      isGraphFocused: true,
    }),
  setSelectedNode: (nodeId: string | null) => set({ selectedNodeId: nodeId }),
  setHighlightedNodes: (nodeIds: string[]) => set({ highlightedNodeIds: nodeIds }),
  setGraphFocused: (focused: boolean) => set({ isGraphFocused: focused }),
  setGraphPreset: (preset: GraphPreset) =>
    set((state) => {
      const nextFilters: GraphFilters = {
        ...PRESET_FILTERS[preset],
        document_id: state.graphFilters.document_id,
      };
      if (state.graphPreset === preset && sameFilters(state.graphFilters, nextFilters)) {
        return state;
      }
      return {
        graphPreset: preset,
        graphFilters: nextFilters,
      };
    }),
  setSelectedDocumentId: (documentId: string | null) =>
    set((state) => {
      const nextDocumentId = documentId || null;
      const nextFilters: GraphFilters = {
        ...state.graphFilters,
        document_id: documentId || undefined,
      };
      if (state.selectedDocumentId === nextDocumentId && sameFilters(state.graphFilters, nextFilters)) {
        return state;
      }
      return {
        selectedDocumentId: nextDocumentId,
        graphFilters: nextFilters,
      };
    }),
  updateGraphFilters: (filters: Partial<GraphFilters>) =>
    set((state) => {
      const nextFilters: GraphFilters = {
        ...state.graphFilters,
        ...filters,
      };
      if (sameFilters(state.graphFilters, nextFilters)) {
        return state;
      }
      return { graphFilters: nextFilters };
    }),
  requestGraphRefresh: () =>
    set((state) => ({
      graphRefreshToken: state.graphRefreshToken + 1,
    })),
  setSelectedNodeContext: (context: NodeContext | null) => set({ selectedNodeContext: context }),
}));
