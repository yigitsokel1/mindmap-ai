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


def test_insight_builder_skips_low_diversity_clusters():
    builder = InsightBuilder()
    weak_cluster = EvidenceClusterItem(
        cluster_key="single::USES::snippet",
        entity="SingleMention",
        relation_type="USES",
        evidences=[
            SemanticEvidenceItem(
                relation_type="USES",
                snippet="Single mention in one source.",
                related_node_ids=["n-weak"],
                document_id="doc-1",
            )
        ],
        canonical_frequency=1,
        citation_count=0,
        importance=0.2,
    )

    insights = builder.build([weak_cluster])
    assert insights == []


def test_insight_builder_avoids_trend_from_single_weak_mention():
    builder = InsightBuilder()
    cluster = EvidenceClusterItem(
        cluster_key="trend::USES::snippet",
        entity="SparseMethod",
        relation_type="USES",
        evidences=[
            SemanticEvidenceItem(
                relation_type="USES",
                snippet="Sparse mention in doc one.",
                related_node_ids=["n-1"],
                document_id="doc-1",
            ),
            SemanticEvidenceItem(
                relation_type="USES",
                snippet="Sparse mention in doc two.",
                related_node_ids=["n-1"],
                document_id="doc-2",
            ),
        ],
        canonical_frequency=1,
        citation_count=1,
        importance=0.7,
    )

    insights = builder.build([cluster])
    assert all(item.type != "CROSS_DOCUMENT_TREND" for item in insights)
