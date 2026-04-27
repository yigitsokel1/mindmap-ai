from backend.app.schemas.graph_response import GraphMeta, GraphResponse
from backend.app.schemas.node_detail import NodeDetail, NodeGroupedRelations, NodeRelations


class FakeGraphReader:
    last_filters = None

    def read_graph(self, filters):
        FakeGraphReader.last_filters = filters
        return GraphResponse(nodes=[], edges=[], meta=GraphMeta(counts={"nodes": 0, "edges": 0}, filters_applied={}))

    def read_node_detail(self, node_id, document_id=None):
        if node_id == "missing":
            return None
        return NodeDetail(
            id=node_id,
            type="Method",
            name="Transformer",
            summary="Node summary",
            metadata={"uid": node_id},
            relations=NodeRelations(incoming=[], outgoing=[]),
            grouped_relations=NodeGroupedRelations(
                incoming=[{"relation_type": "SUPPORTED_BY", "count": 1, "items": []}],
                outgoing=[{"relation_type": "USES", "count": 2, "items": []}],
            ),
            evidences=[
                {
                    "text": "evidence snippet",
                    "passage_id": "p-1",
                    "document_id": "doc-1",
                    "document_name": "paper_a.pdf",
                    "page": 3,
                }
            ],
            citations=[{"title": "Ref", "label": "[1]"}],
            linked_canonical_entity={"uid": "canonical_method:transformer", "canonical_name": "Transformer"},
            canonical_aliases=["transformer architecture"],
            canonical_alias_count=1,
            canonical_link_reason="normalized_exact_match",
            canonical_link_confidence=0.99,
            appears_in_documents=2,
            top_related_documents=["paper_a.pdf", "paper_b.pdf"],
            document_distribution=[{"document": "paper_a.pdf", "count": 1}],
        )


def test_graph_semantic_endpoint_empty_graph_contract(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/semantic")
    assert response.status_code == 200
    body = response.json()
    assert body["nodes"] == []
    assert body["edges"] == []
    assert body["meta"]["counts"] == {"nodes": 0, "edges": 0}


def test_graph_semantic_endpoint_node_types_csv_parsing(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/semantic?node_types=Method,Concept")
    assert response.status_code == 200
    assert FakeGraphReader.last_filters.node_types == ["Method", "Concept"]


def test_graph_semantic_endpoint_node_types_repeated_parsing(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/semantic?node_types=Method&node_types=Concept")
    assert response.status_code == 200
    assert FakeGraphReader.last_filters.node_types == ["Method", "Concept"]


def test_graph_semantic_endpoint_document_filter_passthrough(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/semantic?document_id=doc-42")
    assert response.status_code == 200
    assert FakeGraphReader.last_filters.document_id == "doc-42"


def test_graph_semantic_endpoint_document_filter_element_id_passthrough(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/semantic?document_id=4:abc-def:19")
    assert response.status_code == 200
    assert FakeGraphReader.last_filters.document_id == "4:abc-def:19"


def test_graph_node_detail_endpoint_contract(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/node/n-1")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "n-1"
    assert body["type"] == "Method"
    assert "metadata" in body
    assert "grouped_relations" in body
    assert body["summary"]
    assert body["evidences"]
    assert body["citations"]
    assert body["linked_canonical_entity"]["canonical_name"] == "Transformer"
    assert body["appears_in_documents"] == 2
    assert body["canonical_link_reason"] == "normalized_exact_match"
    assert body["canonical_link_confidence"] == 0.99
    assert body["document_distribution"][0]["document"] == "paper_a.pdf"


def test_graph_node_detail_endpoint_not_found(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/node/missing")
    assert response.status_code == 404
