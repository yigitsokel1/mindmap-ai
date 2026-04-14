from backend.app.schemas.document_structure import ReferenceRecord, SectionRecord
from backend.app.services.parsing.document_parser import parse_document
from backend.app.services.parsing.pdf_parser import PageRecord


def test_parse_document_separates_references_and_body(monkeypatch):
    import backend.app.services.parsing.document_parser as module

    pages = [
        PageRecord(page_number=0, text="Introduction\nBody cites [1]."),
        PageRecord(page_number=1, text="References\n[1] Smith, J. Test Paper. 2020."),
    ]
    sections = [
        SectionRecord(
            section_id="sec-intro",
            document_id="doc-1",
            title="Introduction",
            level=1,
            ordinal=0,
            page_start=0,
            page_end=0,
        ),
        SectionRecord(
            section_id="sec-ref",
            document_id="doc-1",
            title="References",
            level=1,
            ordinal=1,
            page_start=1,
            page_end=1,
        ),
    ]

    monkeypatch.setattr(module, "parse_pdf", lambda _: pages)
    monkeypatch.setattr(module, "detect_sections", lambda *_args, **_kwargs: sections)
    monkeypatch.setattr(module, "find_references_boundary", lambda _sections: 1)
    monkeypatch.setattr(
        module,
        "parse_references",
        lambda *_args, **_kwargs: [
            ReferenceRecord(
                reference_id="ref-1",
                document_id="doc-1",
                raw_text="[1] Smith, J. Test Paper. 2020.",
                order=0,
                year=2020,
                title_guess="Test Paper",
                authors_guess=["Smith"],
                citation_key_numeric=1,
                citation_key_author_year=["smith:2020"],
            )
        ],
    )

    result = parse_document("dummy.pdf", "doc-1", chunk_size=500, chunk_overlap=0)
    assert len(result.passages) == 1
    assert result.passages[0].content_type == "body"
    assert len(result.references) == 1
    assert all(citation.passage_id == result.passages[0].passage_id for citation in result.inline_citations)
