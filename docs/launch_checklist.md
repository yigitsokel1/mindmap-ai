# Launch Checklist

## Required Passes

- [ ] Backend tests pass: `poetry run pytest backend/tests`
- [ ] Semantic synthetic eval passes: `poetry run python backend/tools/run_semantic_eval.py`
- [ ] Real acceptance eval runs: `poetry run python backend/tools/run_semantic_eval.py --profile acceptance_real`
- [ ] Seeded smoke passes: `cd frontend && npm run test:smoke`
- [ ] Baseline measured: `poetry run python backend/tools/measure_baseline.py --document-id doc-transformer`
- [ ] Local run path validated from README and scripts

## Known Limitations

- Baseline script is latency snapshot oriented, not a full benchmark suite.
- Ingest latency measurement requires a local PDF path when running baseline.
- Legacy env keys remain available for backwards compatibility.

## Acceptable Risk List

- Minor variance in smoke timings across machines.
- Partial data responses can occur on degraded graph/database connectivity.
- Frontend fallback messaging is conservative and may hide raw backend detail.

## Next-After-Launch Backlog

- Add CI workflow that runs seeded smoke automatically on every PR.
- Add percentile latency tracking (p50/p95) over repeated runs.
- Add richer provenance assertions for citation-to-passage consistency in e2e.
- Add Docker local stack as optional parallel run path.
