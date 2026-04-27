import { create } from "zustand";
import { DEFAULT_SEMANTIC_FILTERS } from "../lib/constants";
import type { ChatTurn, GraphFilters, NodeContext } from "../lib/types";

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
  mode: "semantic";
  chatTurns: ChatTurn[];

  // Inspector state
  isPDFViewerOpen: boolean;
  pdfUrl: string | null;
  pdfDocName: string | null;
  pdfPage: number | null;
  selectedNodeContext: NodeContext | null;
  setSelectedNodeContext: (context: NodeContext | null) => void;

  // Graph state
  selectedNodeId: string | null;
  primaryFocusNodeId: string | null;
  secondaryFocusNodeIds: string[];
  highlightedNodeIds: string[];
  isGraphFocused: boolean;
  graphFilters: GraphFilters;
  graphRefreshToken: number;
  graphFocusRelevantOnly: boolean;

  // Document/filter state
  selectedDocumentId: string | null;

  // Inspector actions
  openPDFViewer: (url: string, docName: string, page: number) => void;
  closePDFViewer: () => void;

  // Query/UI actions
  toggleCommandCenter: () => void;
  appendChatTurn: (turn: ChatTurn) => void;
  clearChatTurns: () => void;

  // Graph actions
  setSelectedNode: (nodeId: string | null) => void;
  setGraphFocusNodes: (primaryNodeId: string | null, secondaryNodeIds: string[]) => void;
  setHighlightedNodes: (nodeIds: string[]) => void;
  setGraphFocused: (focused: boolean) => void;
  updateGraphFilters: (filters: Partial<GraphFilters>) => void;
  requestGraphRefresh: () => void;
  setGraphFocusRelevantOnly: (enabled: boolean) => void;

  // Document/filter actions
  setSelectedDocumentId: (documentId: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial State
  isCommandCenterOpen: true,
  mode: "semantic",
  chatTurns: [],
  isPDFViewerOpen: false,
  selectedNodeContext: null,
  selectedNodeId: null,
  primaryFocusNodeId: null,
  secondaryFocusNodeIds: [],
  pdfUrl: null,
  pdfDocName: null,
  pdfPage: null,
  highlightedNodeIds: [],
  isGraphFocused: true,
  graphFilters: { ...DEFAULT_SEMANTIC_FILTERS },
  graphRefreshToken: 0,
  graphFocusRelevantOnly: false,
  selectedDocumentId: null,
  
  // Actions
  toggleCommandCenter: () => set((state) => ({ isCommandCenterOpen: !state.isCommandCenterOpen })),
  appendChatTurn: (turn: ChatTurn) => set((state) => ({ chatTurns: [...state.chatTurns, turn] })),
  clearChatTurns: () => set({ chatTurns: [] }),
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
  setGraphFocusNodes: (primaryNodeId: string | null, secondaryNodeIds: string[]) =>
    set(() => {
      const dedupedSecondary = Array.from(new Set(secondaryNodeIds.filter((nodeId) => nodeId && nodeId !== primaryNodeId)));
      const highlightedNodeIds = primaryNodeId ? [primaryNodeId, ...dedupedSecondary] : dedupedSecondary;
      return {
        primaryFocusNodeId: primaryNodeId,
        secondaryFocusNodeIds: dedupedSecondary,
        highlightedNodeIds,
      };
    }),
  setHighlightedNodes: (nodeIds: string[]) => set({ highlightedNodeIds: nodeIds }),
  setGraphFocused: (focused: boolean) => set({ isGraphFocused: focused }),
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
  setGraphFocusRelevantOnly: (enabled: boolean) => set({ graphFocusRelevantOnly: enabled }),
  setSelectedNodeContext: (context: NodeContext | null) => set({ selectedNodeContext: context }),
}));
