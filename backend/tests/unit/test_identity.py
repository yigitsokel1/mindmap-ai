from backend.app.domain.identity import build_entity_uid, build_relation_instance_uid


def test_build_entity_uid_is_deterministic_and_slugged():
    uid = build_entity_uid("Method", "WMT 2014 English-German")
    assert uid == "method:wmt-2014-english-german"


def test_build_entity_uid_normalizes_unicode_and_punctuation():
    uid = build_entity_uid("Concept", "Café-Driven, Attention!!!")
    assert uid == "concept:cafe-driven-attention"


def test_build_relation_instance_uid_uses_slugged_relation_and_endpoints():
    uid = build_relation_instance_uid(
        "EVALUATED_ON",
        "method:transformer",
        "dataset:wmt-2014",
    )
    assert uid == "ri:evaluated-on:method:transformer:dataset:wmt-2014"
