from backend.app.schemas.graph_response import GraphMeta, GraphResponse
from backend.app.schemas.node_detail import NodeDetail, NodeRelations


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
            evidences=[],
            citations=[],
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


def test_graph_node_detail_endpoint_contract(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/node/n-1")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "n-1"
    assert body["type"] == "Method"
    assert "metadata" in body


def test_graph_node_detail_endpoint_not_found(api_client, monkeypatch):
    import backend.app.api.graph as graph_api

    monkeypatch.setattr(graph_api, "SemanticGraphReader", FakeGraphReader)
    response = api_client.get("/api/graph/node/missing")
    assert response.status_code == 404
