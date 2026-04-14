from backend.app.schemas.graph_response import GraphEdge
from backend.app.services.query.semantic_graph_reader import SemanticGraphFilters, SemanticGraphReader


class FakeNode:
    def __init__(self, element_id: str, labels: list[str], props: dict):
        self.element_id = element_id
        self.labels = labels
        self._props = props

    def items(self):
        return self._props.items()


def test_read_graph_shapes_nodes_edges_and_meta(monkeypatch):
    reader = object.__new__(SemanticGraphReader)
    reader.BASE_NODE_TYPES = SemanticGraphReader.BASE_NODE_TYPES
    reader.STRUCTURAL_NODE_TYPES = SemanticGraphReader.STRUCTURAL_NODE_TYPES
    reader.EVIDENCE_NODE_TYPES = SemanticGraphReader.EVIDENCE_NODE_TYPES
    reader.CITATION_NODE_TYPES = SemanticGraphReader.CITATION_NODE_TYPES
    reader.SUPPORTED_NODE_TYPES = SemanticGraphReader.SUPPORTED_NODE_TYPES

    node_a = FakeNode("n1", ["Method"], {"canonical_name": "Transformer"})
    node_b = FakeNode("n2", ["Concept"], {"name": "Attention"})
    monkeypatch.setattr(reader, "_load_nodes", lambda *_args, **_kwargs: [{"n": node_a}, {"n": node_b}])
    monkeypatch.setattr(reader, "_load_edges", lambda _node_ids: [
        GraphEdge(id="r1", source="n1", target="n2", type="USES", properties={"confidence": 0.9})
    ])

    filters = SemanticGraphFilters(
        document_id="doc-1",
        node_types=[],
        include_structural=True,
        include_evidence=False,
        include_citations=False,
    )
    result = reader.read_graph(filters)

    assert len(result.nodes) == 2
    assert result.nodes[0].display_name in {"Transformer", "Attention"}
    assert len(result.edges) == 1
    assert result.meta.counts == {"nodes": 2, "edges": 1}
    assert result.meta.filters_applied["document_id"] == "doc-1"


def test_resolve_labels_applies_filters_and_include_flags():
    reader = object.__new__(SemanticGraphReader)
    reader.BASE_NODE_TYPES = SemanticGraphReader.BASE_NODE_TYPES
    reader.STRUCTURAL_NODE_TYPES = SemanticGraphReader.STRUCTURAL_NODE_TYPES
    reader.EVIDENCE_NODE_TYPES = SemanticGraphReader.EVIDENCE_NODE_TYPES
    reader.CITATION_NODE_TYPES = SemanticGraphReader.CITATION_NODE_TYPES
    reader.SUPPORTED_NODE_TYPES = SemanticGraphReader.SUPPORTED_NODE_TYPES

    filters = SemanticGraphFilters(
        document_id=None,
        node_types=["Method", "Section", "UnknownLabel"],
        include_structural=True,
        include_evidence=False,
        include_citations=False,
    )
    labels = reader._resolve_labels(filters)

    assert labels == {"Method", "Section"}


def test_read_graph_empty_result_keeps_contract(monkeypatch):
    reader = object.__new__(SemanticGraphReader)
    reader.BASE_NODE_TYPES = SemanticGraphReader.BASE_NODE_TYPES
    reader.STRUCTURAL_NODE_TYPES = SemanticGraphReader.STRUCTURAL_NODE_TYPES
    reader.EVIDENCE_NODE_TYPES = SemanticGraphReader.EVIDENCE_NODE_TYPES
    reader.CITATION_NODE_TYPES = SemanticGraphReader.CITATION_NODE_TYPES
    reader.SUPPORTED_NODE_TYPES = SemanticGraphReader.SUPPORTED_NODE_TYPES
    monkeypatch.setattr(reader, "_load_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(reader, "_load_edges", lambda _node_ids: [])

    result = reader.read_graph(
        SemanticGraphFilters(
            document_id=None,
            node_types=[],
            include_structural=False,
            include_evidence=False,
            include_citations=False,
        )
    )
    assert result.nodes == []
    assert result.edges == []
    assert result.meta.counts == {"nodes": 0, "edges": 0}
