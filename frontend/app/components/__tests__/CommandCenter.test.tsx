import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CommandCenter from "../CommandCenter";
import { useAppStore } from "../../store/useAppStore";

describe("CommandCenter", () => {
  beforeEach(() => {
    useAppStore.setState({
      isCommandCenterOpen: true,
      activeTab: "query",
      selectedDocumentId: null,
      highlightedNodeIds: [],
      selectedNodeContext: null,
    });
  });

  it("renders answer/key insights/clustered evidence/citations hierarchy after semantic query", async () => {
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
          citations: [{ label: "[12]", document_name: "paper.pdf", page: 3 }],
          explanation: {
            why_these_entities: ["entity"],
            why_this_evidence: ["evidence reason"],
            reasoning_path: ["question_intent:SUMMARY"],
            selected_sections: ["Methods"],
            selection_signals: ["citation_signal_weighted_by_intent"],
          },
          confidence: 0.82,
          mode: "semantic_grounded",
        }),
      })
    );

    render(<CommandCenter />);
    fireEvent.change(screen.getByPlaceholderText("ENTER QUERY..."), {
      target: { value: "How does transformer work?" },
    });
    fireEvent.click(screen.getByTitle("Send"));

    await waitFor(() => expect(screen.getByText(/Grounded answer/i)).toBeInTheDocument());
    expect(screen.getByText("Key Points")).toBeInTheDocument();
    expect(screen.getByText("Insights")).toBeInTheDocument();
    expect(screen.getByText("Evidence (Clustered)")).toBeInTheDocument();
    expect(screen.getAllByText("Citations").length).toBeGreaterThan(0);
    expect(screen.getByText("Advanced Reasoning Details")).toBeInTheDocument();
  });
});
