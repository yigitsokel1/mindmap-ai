import { create } from "zustand";
import { PRESET_FILTERS } from "../lib/constants";
import type { GraphFilters, GraphPreset, NodeContext, QueryMode } from "../lib/types";

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
    set((state) => ({
      graphPreset: preset,
      graphFilters: {
        ...PRESET_FILTERS[preset],
        document_id: state.graphFilters.document_id,
      },
    })),
  setSelectedDocumentId: (documentId: string | null) =>
    set((state) => ({
      selectedDocumentId: documentId,
      graphFilters: {
        ...state.graphFilters,
        document_id: documentId || undefined,
      },
    })),
  updateGraphFilters: (filters: Partial<GraphFilters>) =>
    set((state) => ({
      graphFilters: {
        ...state.graphFilters,
        ...filters,
      },
    })),
  setSelectedNodeContext: (context: NodeContext | null) => set({ selectedNodeContext: context }),
}));
