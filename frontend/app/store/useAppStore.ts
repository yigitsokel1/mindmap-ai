import { create } from "zustand";
import { PRESET_FILTERS } from "../lib/constants";
import type { GraphFilters, GraphPreset, NodeContext } from "../lib/types";

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
  // Query/UI state
  isCommandCenterOpen: boolean;
  activeTab: "query" | "files";
  mode: "semantic";

  // Inspector state
  isPDFViewerOpen: boolean;
  selectedNodeContext: NodeContext | null;
  setSelectedNodeContext: (context: NodeContext | null) => void;

  // Graph state
  selectedNodeId: string | null;
  highlightedNodeIds: string[];
  isGraphFocused: boolean;
  graphPreset: GraphPreset;
  graphFilters: GraphFilters;
  graphRefreshToken: number;

  // Document/filter state
  selectedDocumentId: string | null;

  // Inspector actions
  openPDFViewer: (url: string, docName: string, page: number) => void;
  closePDFViewer: () => void;

  // Query/UI actions
  toggleCommandCenter: () => void;
  setActiveTab: (tab: "query" | "files") => void;

  // Graph actions
  setSelectedNode: (nodeId: string | null) => void;
  setHighlightedNodes: (nodeIds: string[]) => void;
  setGraphFocused: (focused: boolean) => void;
  setGraphPreset: (preset: GraphPreset) => void;
  updateGraphFilters: (filters: Partial<GraphFilters>) => void;
  requestGraphRefresh: () => void;

  // Document/filter actions
  setSelectedDocumentId: (documentId: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial State
  isCommandCenterOpen: true,
  activeTab: "query",
  mode: "semantic",
  isPDFViewerOpen: false,
  selectedNodeContext: null,
  selectedNodeId: null,
  pdfUrl: null,
  pdfDocName: null,
  pdfPage: null,
  highlightedNodeIds: [],
  isGraphFocused: true,
  graphPreset: "semantic",
  graphFilters: { ...PRESET_FILTERS.semantic },
  graphRefreshToken: 0,
  selectedDocumentId: null,
  
  // Actions
  toggleCommandCenter: () => set((state) => ({ isCommandCenterOpen: !state.isCommandCenterOpen })),
  setActiveTab: (tab: "query" | "files") => set({ activeTab: tab }),
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
      return {
        graphFilters: nextFilters,
        selectedDocumentId: nextFilters.document_id || null,
      };
    }),
  requestGraphRefresh: () =>
    set((state) => ({
      graphRefreshToken: state.graphRefreshToken + 1,
    })),
  setSelectedNodeContext: (context: NodeContext | null) => set({ selectedNodeContext: context }),
}));
