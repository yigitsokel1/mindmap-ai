import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CommandCenter from "../CommandCenter";
import { useAppStore } from "../../store/useAppStore";

describe("CommandCenter", () => {
  beforeEach(() => {
    useAppStore.setState({
      isCommandCenterOpen: true,
      selectedDocumentId: null,
      highlightedNodeIds: [],
      selectedNodeContext: null,
    });
  });

  it("renders compact answer, source, and details sections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: "Grounded answer",
          query_intent: "SUMMARY",
          matched_entities: [{ id: "n-1", type: "Method", display_name: "Transformer" }],
          evidence: [
            {
              relation_type: "USES",
              snippet: "Transformer uses attention.",
              section: "Methods",
              confidence: 0.9,
              related_node_ids: ["n-1"],
              document_name: "paper.pdf",
              page: 3,
            },
          ],
          related_nodes: [{ id: "n-1", type: "Method", display_name: "Transformer" }],
          primary_focus_node_id: "n-1",
          secondary_focus_node_ids: ["ri-2"],
          focus_seed_ids: ["n-1", "ri-2"],
          citations: [{ label: "[12]", document_name: "paper.pdf", page: 3 }],
          explanation: {
            why_these_entities: ["entity"],
            why_this_evidence: ["evidence reason"],
            reasoning_path: ["question_intent:SUMMARY"],
            selected_sections: ["Methods"],
            selection_signals: ["citation_signal_weighted_by_intent"],
          },
          confidence: 0.82,
          key_points: ["Point A", "Point B"],
          insights: [{ type: "COMMON_PATTERN", text: "Stable pattern", confidence: 0.9, supporting_clusters: ["c-1"] }],
          clusters: [{ cluster_key: "c-1", entity: "Transformer", relation_type: "USES", evidences: [], canonical_frequency: 2, citation_count: 1, importance: 0.8 }],
          mode: "semantic_grounded",
        }),
      })
    );

    render(<CommandCenter />);
    fireEvent.change(screen.getByPlaceholderText("ENTER QUERY..."), {
      target: { value: "How does transformer work?" },
    });
    fireEvent.click(screen.getByTitle("Send"));

    await waitFor(() => expect(screen.getAllByText(/Grounded answer/i).length).toBeGreaterThan(0));
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByTestId("primary-source-button")).toBeInTheDocument();
    expect(screen.getByText("Details")).toBeInTheDocument();
    expect(screen.getByText("Citations")).toBeInTheDocument();
    expect(screen.getByText("Matched Entities")).toBeInTheDocument();
    const highlightedNodeIds = useAppStore.getState().highlightedNodeIds;
    expect(useAppStore.getState().primaryFocusNodeId).toBe("n-1");
    expect(useAppStore.getState().secondaryFocusNodeIds).toContain("ri-2");
    expect(highlightedNodeIds).toContain("n-1");
    expect(highlightedNodeIds).toContain("ri-2");
  });
});
