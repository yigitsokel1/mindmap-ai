from backend.app.services.parsing.pdf_parser import PageRecord
from backend.app.services.parsing.section_detector import detect_sections


def test_detect_sections_supports_common_heading_styles():
    pages = [
        PageRecord(
            page_number=0,
            text="\n".join(
                [
                    "Abstract",
                    "Introduction",
                    "3 Method",
                    "IV EXPERIMENTS",
                    "References",
                ]
            ),
        )
    ]

    sections = detect_sections(pages, document_id="doc-1")
    titles = [item.title for item in sections]

    assert "Abstract" in titles
    assert "Introduction" in titles
    assert "3 Method" in titles
    assert "IV EXPERIMENTS" in titles
    assert "References" in titles
