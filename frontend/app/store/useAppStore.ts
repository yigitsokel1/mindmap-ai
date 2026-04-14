import { create } from "zustand";

interface AppState {
  // UI State
  isCommandCenterOpen: boolean;
  activeTab: "chat" | "files";
  isPDFViewerOpen: boolean;
  selectedNodeId: string | null;
  
  // PDF Viewer State
  pdfUrl: string | null;
  pdfDocName: string | null;
  pdfPage: number | null;
  
  // Graph State
  highlightedNodeIds: string[];
  isGraphFocused: boolean; // For blur/dim effect when panels are open
  
  // Actions
  toggleCommandCenter: () => void;
  setActiveTab: (tab: "chat" | "files") => void;
  openPDFViewer: (url: string, docName: string, page: number) => void;
  closePDFViewer: () => void;
  setSelectedNode: (nodeId: string | null) => void;
  setHighlightedNodes: (nodeIds: string[]) => void;
  setGraphFocused: (focused: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial State
  isCommandCenterOpen: true,
  activeTab: "chat",
  isPDFViewerOpen: false,
  selectedNodeId: null,
  pdfUrl: null,
  pdfDocName: null,
  pdfPage: null,
  highlightedNodeIds: [],
  isGraphFocused: true,
  
  // Actions
  toggleCommandCenter: () => set((state) => ({ isCommandCenterOpen: !state.isCommandCenterOpen })),
  setActiveTab: (tab: "chat" | "files") => set({ activeTab: tab }),
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
}));
