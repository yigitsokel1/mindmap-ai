param(
  [string]$ApiBase = "http://127.0.0.1:8000"
)

Write-Host "MindMap-AI local run path (script-first)"
Write-Host "1) Start Neo4j first (local or cloud URI in .env)."
Write-Host "2) Start backend and frontend in separate terminals:"
Write-Host "   poetry run uvicorn backend.app.main:app --reload"
Write-Host "   cd frontend; npm run dev"
Write-Host "3) Seed deterministic smoke graph:"
poetry run python backend/tools/seed_smoke_graph.py
Write-Host "Seed completed. Use SMOKE_DOCUMENT_ID=doc-transformer"
