# Sprint 23 Phase 1 Acceptance Pack

This acceptance pack validates behavior on real-paper style fixtures.

## Dataset

- `backend/evals/acceptance_real/documents.json`
- `backend/evals/acceptance_real/cases.json`
- `backend/evals/acceptance_real/expected_citations.json`

## Manual Reviewer Expectations

- Each case returns evidence-backed text aligned with the target section.
- Citation/provenance is visible when expected.
- Expected canonical entities are present in matched entities.
- No unsupported claims are made without evidence snippets.

## Run

```bash
poetry run python backend/tools/run_semantic_eval.py --profile acceptance_real
```

## Pass Guidance

- Intent accuracy >= 80%
- Evidence presence >= 90%
- Citation expectation >= 80%
- Section coverage >= 80%
