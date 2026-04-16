from backend.app.schemas.semantic_query import CandidateEntity
from backend.app.services.query.candidate_selector import CandidateSelector
from backend.app.services.query.question_interpreter import InterpretedQuestion


class FakeReader:
    def find_candidate_entities(self, tokens, document_id, node_types, limit=20):  # noqa: ARG002
        return [
            CandidateEntity(
                entity_id="n-1",
                name="Transformer",
                type="Method",
                score=0.7,
                match_reason="token_match",
                source="local",
            )
        ]

    def find_fallback_entities(self, document_id, node_types, intent, limit=5):  # noqa: ARG002
        return []

    def lookup_canonical_candidates(self, tokens):  # noqa: ARG002
        return [
            CandidateEntity(
                entity_id="n-1",
                name="Transformer",
                type="Method",
                score=0.92,
                match_reason="canonical_linked_match",
                source="canonical-ready",
            ),
            CandidateEntity(
                entity_id="n-2",
                name="Attention",
                type="Concept",
                score=0.88,
                match_reason="canonical_linked_match",
                source="canonical-ready",
            ),
        ]


def test_candidate_selector_prefers_canonical_and_deduplicates():
    selector = CandidateSelector(FakeReader())
    interpreted = InterpretedQuestion(
        intent="SUMMARY",
        entity_hints=["transformer"],
        relation_hints=[],
        document_constraints={},
        disambiguation_terms=["transformer"],
    )
    result = selector.select_candidates(
        question="Transformer hangi paperlarda geciyor?",
        interpreted=interpreted,
        document_id="doc-1",
        node_types=[],
    )
    assert len(result) == 2
    assert result[0].entity_id == "n-1"
    assert result[0].source == "canonical-ready"
