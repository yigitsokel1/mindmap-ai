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
        documentName: "paper.pdf",
        page: 3,
      },
    });
  });

  it("renders semantic context with source and open action", async () => {
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
          linked_canonical_entity: { canonical_name: "Transformer", uid: "canonical_method:transformer" },
          canonical_aliases: ["Transformer architecture"],
          appears_in_documents: 3,
          top_related_documents: ["paper_a.pdf", "paper_b.pdf"],
        }),
      })
    );

    render(<Inspector />);
    await waitFor(() => expect(screen.getAllByText("paper.pdf · page 3").length).toBeGreaterThan(0));
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getAllByText("Node summary").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /open pdf/i })).toBeInTheDocument();
  });

  it("derives source from node evidences when context source is missing", async () => {
    useAppStore.setState({
      isPDFViewerOpen: false,
      selectedDocumentId: "doc-1",
      selectedNodeContext: {
        id: "n-2",
        label: "Method",
        title: "Fallback Node",
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "n-2",
          type: "Method",
          name: "Fallback Node",
          summary: "Node summary",
          metadata: {},
          relations: { incoming: [], outgoing: [] },
          grouped_relations: { incoming: [], outgoing: [] },
          evidences: [
            {
              text: "fallback snippet",
              passage_id: "p-2",
              document_id: "doc-1",
              document_name: "fallback.pdf",
              page: 7,
            },
          ],
          citations: [],
        }),
      })
    );

    render(<Inspector />);
    await waitFor(() => expect(screen.getByText("fallback.pdf · page 7")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /open pdf/i })).toBeInTheDocument();
  });

  it("shows derived semantic fallback when no source exists", async () => {
    useAppStore.setState({
      isPDFViewerOpen: false,
      selectedDocumentId: "doc-1",
      selectedNodeContext: {
        id: "n-3",
        label: "Concept",
        title: "Derived Concept",
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "n-3",
          type: "Concept",
          name: "Derived Concept",
          summary: "",
          metadata: {},
          relations: { incoming: [], outgoing: [] },
          grouped_relations: { incoming: [], outgoing: [] },
          evidences: [],
          citations: [],
        }),
      })
    );

    render(<Inspector />);
    await waitFor(() =>
      expect(screen.getByText("Derived semantic node (not directly from document)")).toBeInTheDocument()
    );
  });
});
