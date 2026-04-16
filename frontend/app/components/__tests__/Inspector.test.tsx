import { render, screen, waitFor } from "@testing-library/react";
import Inspector from "../Inspector";
import { useAppStore } from "../../store/useAppStore";

describe("Inspector", () => {
  beforeEach(() => {
    useAppStore.setState({
      isPDFViewerOpen: false,
      selectedDocumentId: "doc-1",
      selectedNodeContext: {
        id: "n-1",
        label: "Method",
        title: "Transformer",
      },
    });
  });

  it("renders grouped relations and summary from node detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "n-1",
          type: "Method",
          name: "Transformer",
          summary: "Node summary",
          metadata: {},
          relations: { incoming: [], outgoing: [] },
          grouped_relations: {
            incoming: [{ relation_type: "SUPPORTED_BY", count: 1, items: [] }],
            outgoing: [{ relation_type: "USES", count: 2, items: [] }],
          },
          evidences: [{ text: "evidence snippet", passage_id: "p-1", document_id: "doc-1" }],
          citations: [{ title: "Ref", label: "[1]" }],
        }),
      })
    );

    render(<Inspector />);
    await waitFor(() => expect(screen.getByText("Node summary")).toBeInTheDocument());
    expect(screen.getByText("Incoming Relations")).toBeInTheDocument();
    expect(screen.getByText("Outgoing Relations")).toBeInTheDocument();
    expect(screen.getByText("Top Evidence Snippets")).toBeInTheDocument();
    expect(screen.getByText("Linked Citations")).toBeInTheDocument();
  });
});
