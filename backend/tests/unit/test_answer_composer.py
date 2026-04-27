from backend.app.schemas.semantic_query import CandidateEntity, SemanticEvidenceItem
from backend.app.services.query.answer_composer import AnswerComposer


def _candidate(entity_id: str, name: str) -> CandidateEntity:
    return CandidateEntity(
        entity_id=entity_id,
        type="Method",
        name=name,
        score=0.9,
        match_reason="test",
        source="local",
    )


def _evidence(snippet: str, relation_type: str = "USES") -> SemanticEvidenceItem:
    return SemanticEvidenceItem(
        relation_type=relation_type,
        snippet=snippet,
        section="Methods",
        confidence=0.8,
        related_node_ids=["n-1"],
        document_id="doc-1",
        document_name="paper.pdf",
    )


def test_compose_returns_no_grounding_text_without_candidates():
    composer = AnswerComposer()

    answer = composer.compose(
        question="What is YOLO?",
        query_intent="SUMMARY",
        evidence=[],
        candidates=[],
    )

    assert "No semantic grounding found" in answer


def test_apply_guardrails_marks_weak_match_as_limited():
    composer = AnswerComposer()

    guarded, limited, uncertain, reason = composer.apply_guardrails(
        answer_text="Transformer is used in retrieval.",
        query_intent="METHOD_USAGE",
        evidence=[_evidence("Transformer is used in retrieval.")],
        citations=[],
        confidence=0.4,
    )

    assert limited is True
    assert uncertain is True
    assert reason == "weak_match"
    assert "limited evidence" in guarded.lower()


def test_dedupe_evidence_keeps_first_unique_snippets():
    composer = AnswerComposer()
    evidence = [
        _evidence("Transformer uses self attention."),
        _evidence(" Transformer uses self  attention. "),
        _evidence("It improves latency."),
    ]

    deduped = composer.dedupe_evidence(evidence, limit=3)

    assert len(deduped) == 2
    assert deduped[0].snippet == "Transformer uses self attention."
    assert deduped[1].snippet == "It improves latency."


def test_compose_method_usage_references_evidence_and_second_candidate():
    composer = AnswerComposer()

    answer = composer.compose(
        question="How is Transformer used?",
        query_intent="METHOD_USAGE",
        evidence=[_evidence("Transformer uses self-attention.", "SUPPORTS_METHOD")],
        candidates=[_candidate("n1", "Transformer"), _candidate("n2", "Self-Attention")],
    )

    assert "Transformer" in answer
    assert "Self-Attention" in answer
    assert "Evidence:" in answer
