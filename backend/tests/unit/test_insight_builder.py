from backend.app.schemas.semantic_query import EvidenceClusterItem, SemanticEvidenceItem
from backend.app.services.query.insight_builder import InsightBuilder


def test_insight_builder_generates_cross_document_trend():
    builder = InsightBuilder()
    cluster = EvidenceClusterItem(
        cluster_key="transformer::USES::snippet",
        entity="Transformer",
        relation_type="USES",
        evidences=[
            SemanticEvidenceItem(
                relation_type="USES",
                snippet="A",
                related_node_ids=["n-1"],
                document_id="doc-1",
            ),
            SemanticEvidenceItem(
                relation_type="USES",
                snippet="B",
                related_node_ids=["n-1"],
                document_id="doc-2",
            ),
        ],
        canonical_frequency=2,
        citation_count=0,
        importance=0.7,
    )

    insights = builder.build([cluster])
    types = {item.type for item in insights}
    assert "CROSS_DOCUMENT_TREND" in types
    assert all(item.supporting_clusters for item in insights)
