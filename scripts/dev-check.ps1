param(
  [string]$ApiBase = "http://127.0.0.1:8000"
)

Write-Host "Running launch-readiness checks..."
poetry run pytest backend/tests
poetry run python backend/tools/run_semantic_eval.py
poetry run python backend/tools/run_semantic_eval.py --profile acceptance_real
cd frontend
npm run test:smoke
cd ..
poetry run python backend/tools/measure_baseline.py --api-base $ApiBase --document-id doc-transformer
Write-Host "Checks finished."
