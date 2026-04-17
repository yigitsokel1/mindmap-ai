from backend.app.schemas.semantic_query import CandidateEntity, SemanticEvidenceItem
from backend.app.services.query.traversal_executor import TraversalExecutor
from backend.app.services.query.traversal_planner import TraversalPlan


class FakeReader:
    def __init__(self, items):
        self._items = items

    def collect_evidence(self, candidates, max_evidence, document_id, traversal_plan):  # noqa: ARG002
        return list(self._items)


def _item(relation_type: str, confidence: float) -> SemanticEvidenceItem:
    return SemanticEvidenceItem(
        relation_type=relation_type,
        snippet=f"{relation_type} evidence",
        confidence=confidence,
        related_node_ids=["n-1"],
    )


def _plan(max_evidence_per_candidate: int) -> TraversalPlan:
    return TraversalPlan(
        strategy="test",
        relation_directions=["outgoing"],
        prioritize_citations=False,
        max_candidate_nodes=10,
        max_evidence_per_candidate=max_evidence_per_candidate,
        max_depth=2,
        relation_whitelist=["USES"],
    )


def test_traversal_executor_enforces_relation_whitelist():
    executor = TraversalExecutor()
    reader = FakeReader([_item("USES", 0.8), _item("MENTIONS", 0.9)])
    plan = _plan(max_evidence_per_candidate=4)
    result = executor.execute(
        reader=reader,
        candidates=[CandidateEntity(entity_id="n-1", name="Transformer", type="Method", match_reason="x")],
        max_evidence=4,
        document_id="doc-1",
        traversal_plan=plan,
    )

    assert len(result) == 1
    assert result[0].relation_type == "USES"


def test_traversal_executor_suppresses_repeated_weak_paths():
    executor = TraversalExecutor()
    reader = FakeReader(
        [
            _item("USES", 0.4),
            _item("USES", 0.3),
            _item("USES", 0.2),
            _item("USES", 0.9),
        ]
    )
    plan = _plan(max_evidence_per_candidate=6)
    result = executor.execute(
        reader=reader,
        candidates=[CandidateEntity(entity_id="n-1", name="Transformer", type="Method", match_reason="x")],
        max_evidence=6,
        document_id="doc-1",
        traversal_plan=plan,
    )

    weak = [item for item in result if item.confidence < 0.55]
    assert len(weak) == 2
    assert any(item.confidence >= 0.9 for item in result)
