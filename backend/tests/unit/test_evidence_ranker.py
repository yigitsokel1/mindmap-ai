from backend.app.schemas.semantic_query import SemanticEvidenceItem
from backend.app.services.query.evidence_ranker import EvidenceRanker
from backend.app.services.query.question_interpreter import InterpretedQuestion


def _interpreted(intent: str) -> InterpretedQuestion:
    return InterpretedQuestion(
        intent=intent,
        entity_hints=["transformer"],
        relation_hints=["use", "support"],
        document_constraints={},
    )


def test_duplicate_penalty_demotes_repeated_passage():
    ranker = EvidenceRanker()
    items = [
        SemanticEvidenceItem(
            relation_type="USES",
            snippet="Transformer uses attention blocks.",
            section="Methods",
            confidence=0.8,
            related_node_ids=["a"],
            document_id="doc-1",
        ),
        SemanticEvidenceItem(
            relation_type="USES",
            snippet="Transformer uses attention blocks.",
            section="Methods",
            confidence=0.8,
            related_node_ids=["b"],
            document_id="doc-2",
        ),
        SemanticEvidenceItem(
            relation_type="USES",
            snippet="Distinct evidence snippet for usage.",
            section="Methods",
            confidence=0.8,
            related_node_ids=["c"],
            document_id="doc-3",
        ),
    ]
    ranked = ranker.rank(items, _interpreted("METHOD_USAGE"), candidate_names=["Transformer"])
    assert ranked[0].snippet == "Distinct evidence snippet for usage."


def test_citation_bonus_improves_rank():
    ranker = EvidenceRanker()
    with_citation = SemanticEvidenceItem(
        relation_type="SUPPORTS_METHOD",
        snippet="Citation-backed support.",
        section="Methods",
        confidence=0.5,
        related_node_ids=["a"],
        citation_label="[12]",
        reference_entry_id="ref-1",
    )
    without_citation = SemanticEvidenceItem(
        relation_type="SUPPORTS_METHOD",
        snippet="Non citation support.",
        section="Methods",
        confidence=0.5,
        related_node_ids=["b"],
    )
    ranked = ranker.rank([without_citation, with_citation], _interpreted("CITATION_BASIS"), ["Transformer"])
    assert ranked[0].citation_label == "[12]"


def test_method_intent_prioritizes_methods_section():
    ranker = EvidenceRanker()
    abstract_item = SemanticEvidenceItem(
        relation_type="SUPPORTS_METHOD",
        snippet="Abstract mention of transformer usage.",
        section="Abstract",
        confidence=0.6,
        related_node_ids=["a"],
    )
    methods_item = SemanticEvidenceItem(
        relation_type="SUPPORTS_METHOD",
        snippet="Detailed method usage evidence.",
        section="Methods",
        confidence=0.6,
        related_node_ids=["b"],
    )
    ranked = ranker.rank([abstract_item, methods_item], _interpreted("METHOD_USAGE"), ["Transformer"])
    assert ranked[0].section == "Methods"
