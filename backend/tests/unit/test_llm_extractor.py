import pytest

from backend.app.services.extraction.llm_extractor import LLMExtractor


def _build_extractor_without_init() -> LLMExtractor:
    extractor = object.__new__(LLMExtractor)
    extractor.model = "test-model"
    extractor.client = None
    return extractor


def test_safe_parse_extracts_json_from_wrapped_text():
    extractor = _build_extractor_without_init()

    wrapped = 'noise before {"entities": [], "relations": []} noise after'

    parsed = extractor._safe_parse(wrapped)

    assert parsed == {"entities": [], "relations": []}


def test_safe_parse_raises_for_unparseable_text():
    extractor = _build_extractor_without_init()

    with pytest.raises(ValueError, match="unparseable"):
        extractor._safe_parse("totally not json")


def test_extract_batch_rejects_more_than_three_passages():
    extractor = _build_extractor_without_init()

    passages = [
        {"index": 0, "text": "a"},
        {"index": 1, "text": "b"},
        {"index": 2, "text": "c"},
        {"index": 3, "text": "d"},
    ]

    with pytest.raises(ValueError, match="up to 3 passages"):
        extractor.extract_batch(passages)


def test_filter_invalid_drops_unknown_entity_and_relation_types():
    extractor = _build_extractor_without_init()

    data = {
        "entities": [
            {"type": "Method", "name": "Transformer", "confidence": 0.9},
            {"type": "UnknownType", "name": "Noise", "confidence": 0.9},
        ],
        "relations": [
            {"type": "USES", "source": "Transformer", "target": "Dataset", "confidence": 0.8},
            {"type": "NOT_A_REL", "source": "A", "target": "B", "confidence": 0.8},
        ],
    }

    filtered = extractor._filter_invalid(data)

    assert len(filtered["entities"]) == 1
    assert filtered["entities"][0]["type"] == "Method"
    assert len(filtered["relations"]) == 1
    assert filtered["relations"][0]["type"] == "USES"
