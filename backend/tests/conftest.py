from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.extract import router as extract_router
from backend.app.api.graph import router as graph_router


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text() -> dict[str, str]:
    return {
        "academic": (FIXTURES_DIR / "academic_short.txt").read_text(encoding="utf-8"),
        "sectioned": (FIXTURES_DIR / "sectioned_sample.txt").read_text(encoding="utf-8"),
        "numeric_citations": (FIXTURES_DIR / "numeric_citations.txt").read_text(encoding="utf-8"),
        "author_year_citations": (FIXTURES_DIR / "author_year_citations.txt").read_text(encoding="utf-8"),
        "reference_block": (FIXTURES_DIR / "reference_block.txt").read_text(encoding="utf-8"),
    }


@pytest.fixture
def api_client() -> TestClient:
    app = FastAPI()
    app.include_router(extract_router, prefix="/api")
    app.include_router(graph_router, prefix="/api")
    with TestClient(app) as client:
        yield client
