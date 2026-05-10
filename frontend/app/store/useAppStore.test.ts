import { beforeEach, describe, expect, it } from "vitest";
import { useAppStore } from "./useAppStore";

const INITIAL_UPLOAD_STATE = {
  isUploading: false,
  isServerProcessing: false,
  uploadProgress: 0,
  ingestMessage: null,
  uploadError: null,
};

beforeEach(() => {
  useAppStore.setState({
    chatTurns: [],
    isPDFViewerOpen: false,
    pdfUrl: null,
    pdfDocName: null,
    pdfPage: null,
    pdfSnippet: null,
    selectedNodeId: null,
    primaryFocusNodeId: null,
    secondaryFocusNodeIds: [],
    highlightedNodeIds: [],
    graphRefreshToken: 0,
    selectedDocumentId: null,
    isGraphFocused: true,
    graphFilters: { include_structural: true, include_evidence: true, include_citations: true },
    uploadUiState: { ...INITIAL_UPLOAD_STATE },
  });
});

// ── openPDFViewer / closePDFViewer ────────────────────────────────────────────

describe("openPDFViewer", () => {
  it("sets all viewer fields and marks graph as unfocused", () => {
    useAppStore.getState().openPDFViewer("http://cdn/f.pdf", "Doc A", 5, "some snippet");
    const s = useAppStore.getState();
    expect(s.isPDFViewerOpen).toBe(true);
    expect(s.pdfUrl).toBe("http://cdn/f.pdf");
    expect(s.pdfDocName).toBe("Doc A");
    expect(s.pdfPage).toBe(5);
    expect(s.pdfSnippet).toBe("some snippet");
    expect(s.isGraphFocused).toBe(false);
  });

  it("defaults pdfSnippet to null when snippet is omitted", () => {
    useAppStore.getState().openPDFViewer("http://cdn/f.pdf", "Doc", 1);
    expect(useAppStore.getState().pdfSnippet).toBeNull();
  });

  it("defaults pdfSnippet to null when snippet is explicitly null", () => {
    useAppStore.getState().openPDFViewer("http://cdn/f.pdf", "Doc", 1, null);
    expect(useAppStore.getState().pdfSnippet).toBeNull();
  });
});

describe("closePDFViewer", () => {
  it("clears all viewer fields and restores graph focus", () => {
    useAppStore.getState().openPDFViewer("http://cdn/f.pdf", "Doc", 3, "snip");
    useAppStore.getState().closePDFViewer();
    const s = useAppStore.getState();
    expect(s.isPDFViewerOpen).toBe(false);
    expect(s.pdfUrl).toBeNull();
    expect(s.pdfDocName).toBeNull();
    expect(s.pdfPage).toBeNull();
    expect(s.pdfSnippet).toBeNull();
    expect(s.isGraphFocused).toBe(true);
  });
});

// ── appendChatTurn / clearChatTurns ──────────────────────────────────────────

describe("appendChatTurn", () => {
  it("adds turns in order", () => {
    const { appendChatTurn } = useAppStore.getState();
    appendChatTurn({ id: "t1", role: "user", text: "hello" });
    appendChatTurn({ id: "t2", role: "system", text: "world" });
    const turns = useAppStore.getState().chatTurns;
    expect(turns).toHaveLength(2);
    expect(turns[0].id).toBe("t1");
    expect(turns[1].id).toBe("t2");
  });
});

describe("clearChatTurns", () => {
  it("empties the chat history", () => {
    useAppStore.getState().appendChatTurn({ id: "t1", role: "user", text: "q" });
    useAppStore.getState().clearChatTurns();
    expect(useAppStore.getState().chatTurns).toHaveLength(0);
  });
});

// ── setGraphFocusNodes ────────────────────────────────────────────────────────

describe("setGraphFocusNodes", () => {
  it("sets primary and secondary and computes highlighted", () => {
    useAppStore.getState().setGraphFocusNodes("n1", ["n2", "n3"]);
    const s = useAppStore.getState();
    expect(s.primaryFocusNodeId).toBe("n1");
    expect(s.secondaryFocusNodeIds).toEqual(["n2", "n3"]);
    expect(s.highlightedNodeIds).toContain("n1");
    expect(s.highlightedNodeIds).toContain("n2");
    expect(s.highlightedNodeIds).toContain("n3");
  });

  it("deduplicates secondary ids", () => {
    useAppStore.getState().setGraphFocusNodes("n1", ["n2", "n2", "n3"]);
    const secondary = useAppStore.getState().secondaryFocusNodeIds;
    expect(secondary.filter((id) => id === "n2")).toHaveLength(1);
  });

  it("excludes primary id from secondary list", () => {
    useAppStore.getState().setGraphFocusNodes("n1", ["n1", "n2"]);
    expect(useAppStore.getState().secondaryFocusNodeIds).not.toContain("n1");
  });

  it("includes primary node in highlightedNodeIds first", () => {
    useAppStore.getState().setGraphFocusNodes("n1", ["n2"]);
    expect(useAppStore.getState().highlightedNodeIds[0]).toBe("n1");
  });

  it("handles null primary gracefully", () => {
    useAppStore.getState().setGraphFocusNodes(null, ["n2"]);
    const s = useAppStore.getState();
    expect(s.primaryFocusNodeId).toBeNull();
    expect(s.highlightedNodeIds).toContain("n2");
  });
});

// ── requestGraphRefresh ───────────────────────────────────────────────────────

describe("requestGraphRefresh", () => {
  it("increments graphRefreshToken on each call", () => {
    useAppStore.getState().requestGraphRefresh();
    expect(useAppStore.getState().graphRefreshToken).toBe(1);
    useAppStore.getState().requestGraphRefresh();
    expect(useAppStore.getState().graphRefreshToken).toBe(2);
  });
});

// ── setSelectedDocumentId ─────────────────────────────────────────────────────

describe("setSelectedDocumentId", () => {
  it("updates selectedDocumentId and graphFilters.document_id", () => {
    useAppStore.getState().setSelectedDocumentId("doc-1");
    const s = useAppStore.getState();
    expect(s.selectedDocumentId).toBe("doc-1");
    expect(s.graphFilters.document_id).toBe("doc-1");
  });

  it("sets selectedDocumentId to null for empty string", () => {
    useAppStore.getState().setSelectedDocumentId("");
    expect(useAppStore.getState().selectedDocumentId).toBeNull();
  });

  it("returns same state object when called with same document id twice", () => {
    useAppStore.getState().setSelectedDocumentId("doc-1");
    const before = useAppStore.getState();
    useAppStore.getState().setSelectedDocumentId("doc-1");
    const after = useAppStore.getState();
    expect(after).toBe(before);
  });
});

// ── setUploadUiState / resetUploadUiState ─────────────────────────────────────

describe("setUploadUiState", () => {
  it("patches only the specified fields", () => {
    useAppStore.getState().setUploadUiState({ isUploading: true, uploadProgress: 50 });
    const state = useAppStore.getState().uploadUiState;
    expect(state.isUploading).toBe(true);
    expect(state.uploadProgress).toBe(50);
    expect(state.uploadError).toBeNull();
    expect(state.ingestMessage).toBeNull();
  });

  it("accumulates multiple patches", () => {
    useAppStore.getState().setUploadUiState({ isUploading: true });
    useAppStore.getState().setUploadUiState({ uploadProgress: 75 });
    const state = useAppStore.getState().uploadUiState;
    expect(state.isUploading).toBe(true);
    expect(state.uploadProgress).toBe(75);
  });
});

describe("resetUploadUiState", () => {
  it("restores all fields to initial values", () => {
    useAppStore.getState().setUploadUiState({
      isUploading: true,
      isServerProcessing: true,
      uploadProgress: 80,
      ingestMessage: "Parsing",
      uploadError: "err",
    });
    useAppStore.getState().resetUploadUiState();
    expect(useAppStore.getState().uploadUiState).toEqual(INITIAL_UPLOAD_STATE);
  });
});

// ── toggleCommandCenter ───────────────────────────────────────────────────────

describe("toggleCommandCenter", () => {
  it("flips isCommandCenterOpen each call", () => {
    const initial = useAppStore.getState().isCommandCenterOpen;
    useAppStore.getState().toggleCommandCenter();
    expect(useAppStore.getState().isCommandCenterOpen).toBe(!initial);
    useAppStore.getState().toggleCommandCenter();
    expect(useAppStore.getState().isCommandCenterOpen).toBe(initial);
  });
});
