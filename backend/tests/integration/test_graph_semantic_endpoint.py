from backend.app.schemas.graph_response import GraphMeta, GraphResponse


class FakeGraphReader:
    last_filters = None

    def read_graph(self, filters):
        FakeGraphReader.last_filters = filters
        return GraphResponse(nodes=[], edges=[], meta=GraphMeta(counts={"nodes": 0, "edges": 0}, filters_applied={}))


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
