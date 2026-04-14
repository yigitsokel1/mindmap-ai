from backend.app.schemas.document_structure import SectionRecord
from backend.app.services.parsing.pdf_parser import PageRecord
from backend.app.services.parsing.reference_parser import (
    _extract_authors_guess,
    _extract_year,
    find_references_boundary,
    parse_references,
)


def test_find_references_boundary_handles_numbered_heading():
    sections = [
        SectionRecord(
            section_id="s1",
            document_id="d1",
            title="Introduction",
            level=1,
            ordinal=0,
            page_start=0,
            page_end=0,
        ),
        SectionRecord(
            section_id="s2",
            document_id="d1",
            title="7. References",
            level=1,
            ordinal=1,
            page_start=4,
            page_end=4,
        ),
    ]
    assert find_references_boundary(sections) == 1


def test_parse_references_parses_numeric_entries():
    pages = [
        PageRecord(
            page_number=2,
            text="\n".join(
                [
                    "References",
                    "[1] Vaswani, A. et al. Attention Is All You Need. 2017.",
                    "[2] Smith, J. Evaluation at Scale. 2020.",
                ]
            ),
        )
    ]
    refs = parse_references(pages, ref_start_page=2, document_id="doc-a")
    assert len(refs) == 2
    assert refs[0].citation_key_numeric == 1
    assert refs[1].citation_key_numeric == 2


def test_parse_references_author_year_keys_and_year_extraction():
    pages = [
        PageRecord(
            page_number=1,
            text="\n".join(
                [
                    "References",
                    "Smith, J. Robust Evaluation. ACL. 2020.",
                    "",
                    "Doe, J. Citation Parsing in Practice. EMNLP. 2021.",
                ]
            ),
        )
    ]
    refs = parse_references(pages, ref_start_page=1, document_id="doc-b")
    years = [ref.year for ref in refs]
    assert years == [2020, 2021]
    assert refs[0].citation_key_author_year == ["smith:2020"]


def test_extract_year_prefers_last_year_in_text():
    text = "Published online 2018, conference version 2020."
    assert _extract_year(text) == 2020


def test_extract_authors_guess_basic_case():
    text = "Vaswani et al. Attention Is All You Need. 2017."
    assert _extract_authors_guess(text) == ["Vaswani"]
