from backend.app.services.query.question_interpreter import QuestionInterpreter


def test_interpret_detects_citation_basis_and_document_constraint():
    interpreter = QuestionInterpreter()

    result = interpreter.interpret(
        "Which citations support Transformer claims?",
        document_id="doc-1",
    )

    assert result.intent == "CITATION_BASIS"
    assert result.document_constraints == {"document_id": "doc-1"}
    assert "transformer" in result.entity_hints


def test_interpret_detects_method_usage_from_how_use_pattern():
    interpreter = QuestionInterpreter()

    result = interpreter.interpret("How is retrieval augmented generation used here?")

    assert result.intent == "METHOD_USAGE"
    assert "USES" in result.relation_hints


def test_interpret_extracts_title_case_phrase_first():
    interpreter = QuestionInterpreter()

    result = interpreter.interpret("What is Graph Neural Network limitation?")

    assert "graph neural network" in result.entity_hints
    assert result.intent == "PROBLEM"
