import logging

from backend.app.schemas.graph_response import GraphEdge
from backend.app.services.query.semantic_graph_reader import SemanticGraphFilters, SemanticGraphReader
from backend.app.schemas.node_detail import (
    NodeCitationItem,
    NodeEvidenceItem,
    NodeRelationItem,
)


class FakeNode:
    def __init__(self, element_id: str, labels: list[str], props: dict):
        self.element_id = element_id
        self.labels = labels
        self._props = props

    def items(self):
        return self._props.items()


def test_read_graph_shapes_nodes_edges_and_meta(monkeypatch):
    reader = object.__new__(SemanticGraphReader)
    reader.logger = logging.getLogger("test.semantic_graph_reader")
    reader.BASE_NODE_TYPES = SemanticGraphReader.BASE_NODE_TYPES
    reader.STRUCTURAL_NODE_TYPES = SemanticGraphReader.STRUCTURAL_NODE_TYPES
    reader.EVIDENCE_NODE_TYPES = SemanticGraphReader.EVIDENCE_NODE_TYPES
    reader.CITATION_NODE_TYPES = SemanticGraphReader.CITATION_NODE_TYPES
    reader.SUPPORTED_NODE_TYPES = SemanticGraphReader.SUPPORTED_NODE_TYPES

    node_a = FakeNode("n1", ["Method"], {"canonical_name": "Transformer"})
    node_b = FakeNode("n2", ["Concept"], {"name": "Attention"})
    monkeypatch.setattr(reader, "_load_nodes", lambda *_args, **_kwargs: [{"n": node_a}, {"n": node_b}])
    monkeypatch.setattr(reader, "_load_in_scope_node_ids", lambda _node_ids, _document_id: set(_node_ids))
    monkeypatch.setattr(reader, "_load_edges", lambda _node_ids, in_scope_node_ids=None: [
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
    assert result.meta.counts["nodes"] == 2
    assert result.meta.counts["edges"] == 1
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
    reader.logger = logging.getLogger("test.semantic_graph_reader")
    reader.BASE_NODE_TYPES = SemanticGraphReader.BASE_NODE_TYPES
    reader.STRUCTURAL_NODE_TYPES = SemanticGraphReader.STRUCTURAL_NODE_TYPES
    reader.EVIDENCE_NODE_TYPES = SemanticGraphReader.EVIDENCE_NODE_TYPES
    reader.CITATION_NODE_TYPES = SemanticGraphReader.CITATION_NODE_TYPES
    reader.SUPPORTED_NODE_TYPES = SemanticGraphReader.SUPPORTED_NODE_TYPES
    monkeypatch.setattr(reader, "_load_nodes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(reader, "_load_in_scope_node_ids", lambda _node_ids, _document_id: set())
    monkeypatch.setattr(reader, "_load_edges", lambda _node_ids, in_scope_node_ids=None: [])

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
    assert result.meta.counts["nodes"] == 0
    assert result.meta.counts["edges"] == 0


def test_read_node_detail_shapes_contract(monkeypatch):
    reader = object.__new__(SemanticGraphReader)
    node = FakeNode("n1", ["Method"], {"canonical_name": "Transformer", "summary": "summary"})
    monkeypatch.setattr(reader, "_load_node_by_id", lambda _node_id: {"n": node})
    monkeypatch.setattr(
        reader,
        "_load_relation_neighbors",
        lambda _node_id, direction, document_id=None: [
            NodeRelationItem(id=f"{direction}-1", type="RELATED_TO", name=f"{direction}-node")
        ],
    )
    monkeypatch.setattr(
        reader,
        "_load_node_evidences",
        lambda _node_id, document_id=None: [
            NodeEvidenceItem(text="evidence", passage_id="p1", document_id="doc-1", section="Methods", score=0.8)
        ],
    )
    monkeypatch.setattr(
        reader,
        "_load_node_citations",
        lambda _node_id, document_id=None: [NodeCitationItem(title="Ref", year=2017, label="[1]")],
    )
    monkeypatch.setattr(
        reader,
        "_load_canonical_details",
        lambda _node_id: {"canonical": None, "aliases": [], "document_count": 0, "top_documents": []},
    )

    detail = reader.read_node_detail("n1")
    assert detail is not None
    assert detail.id == "n1"
    assert detail.type == "Method"
    assert detail.name == "Transformer"
    assert detail.evidences[0].text == "evidence"
    assert detail.grouped_relations.incoming[0].relation_type == "RELATED_TO"


def test_group_relations_returns_counted_groups():
    grouped = SemanticGraphReader._group_relations(
        [
            NodeRelationItem(id="a", type="USES", name="A"),
            NodeRelationItem(id="b", type="USES", name="B"),
            NodeRelationItem(id="c", type="IMPROVES", name="C"),
        ]
    )
    assert grouped[0].relation_type == "USES"
    assert grouped[0].count == 2
    assert grouped[1].relation_type == "IMPROVES"


def test_build_node_summary_mentions_importance():
    summary = SemanticGraphReader._build_node_summary(
        node_type="Method",
        node_name="Transformer",
        incoming=[NodeRelationItem(id="i1", type="SUPPORTED_BY", name="PaperA")],
        outgoing=[NodeRelationItem(id="o1", type="USES", name="Attention")],
        evidences=[NodeEvidenceItem(text="e1", passage_id="p1", document_id="doc-1")],
        citations=[NodeCitationItem(title="Ref1", label="[1]")],
        metadata={},
        canonical_info={"canonical": None, "document_count": 0},
    )
    assert "Transformer" in summary
    assert "importance" in summary


def test_read_node_detail_returns_none_for_missing_node(monkeypatch):
    reader = object.__new__(SemanticGraphReader)
    monkeypatch.setattr(reader, "_load_node_by_id", lambda _node_id: None)

    detail = reader.read_node_detail("missing")
    assert detail is None
