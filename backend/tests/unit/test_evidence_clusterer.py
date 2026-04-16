from backend.app.schemas.semantic_query import CandidateEntity, SemanticEvidenceItem
from backend.app.services.query.evidence_clusterer import EvidenceClusterer


def test_clusterer_merges_duplicate_normalized_snippets():
    clusterer = EvidenceClusterer()
    candidates = [CandidateEntity(entity_id="n-1", name="Transformer", type="Method", match_reason="m", source="local")]
    evidence = [
        SemanticEvidenceItem(
            relation_type="USES",
            snippet="Transformer uses attention.",
            related_node_ids=["n-1", "ri-1"],
            citation_label="[1]",
        ),
        SemanticEvidenceItem(
            relation_type="USES",
            snippet="  transformer   uses   attention. ",
            related_node_ids=["n-1", "ri-2"],
        ),
    ]

    clusters = clusterer.build_clusters(evidence, candidates)

    assert len(clusters) == 1
    assert clusters[0].canonical_frequency == 1
    assert clusters[0].citation_count == 1
