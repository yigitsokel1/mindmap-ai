from backend.app.services.parsing.inline_citation_parser import parse_inline_citations


def test_parse_inline_citations_numeric_single_and_list_and_range():
    text = "See [1], [2,5,8], and [3-6] for details."
    citations = parse_inline_citations(text, "doc-1", "pass-1", 0)
    assert len(citations) == 3
    assert citations[0].reference_keys == ["1"]
    assert citations[1].reference_keys == ["2", "5", "8"]
    assert citations[2].reference_keys == ["3", "4", "5", "6"]


def test_parse_inline_citations_author_year_formats():
    text = "As shown in (Vaswani et al., 2017) and (Smith, 2020; Doe, 2021)."
    citations = parse_inline_citations(text, "doc-1", "pass-1", 0)
    author_year = [item for item in citations if item.citation_style == "author_year"]
    assert len(author_year) == 2
    assert author_year[0].reference_labels == ["vaswani:2017"]
    assert author_year[1].reference_labels == ["smith:2020", "doe:2021"]
