from backend.app.services.query.question_interpreter import InterpretedQuestion
from backend.app.services.query.traversal_planner import TraversalPlanner


def _interpreted(intent: str) -> InterpretedQuestion:
    return InterpretedQuestion(
        intent=intent,
        entity_hints=["transformer"],
        relation_hints=["USES"],
        document_constraints={},
        disambiguation_terms=["transformer"],
    )


def test_method_usage_plan_enables_two_hop_with_whitelist():
    planner = TraversalPlanner()
    plan = planner.build_plan(_interpreted("METHOD_USAGE"), max_evidence=6)

    assert plan.max_depth == 2
    assert plan.relation_whitelist == ["USES", "IMPROVES", "BASED_ON", "APPLIED_TO"]


def test_summary_plan_stays_one_hop():
    planner = TraversalPlanner()
    plan = planner.build_plan(_interpreted("SUMMARY"), max_evidence=4)

    assert plan.max_depth == 1
