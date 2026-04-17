# Performance Baseline

This document tracks launch-readiness baseline latency values. These are not throughput benchmarks.

## How To Measure

```bash
poetry run python backend/tools/measure_baseline.py --document-id doc-transformer
```

Optional ingest measurement:

```bash
poetry run python backend/tools/measure_baseline.py --document-id doc-transformer --pdf-path backend/uploaded_docs/attention_is_all_you_need.pdf
```

## Dataset

- Seed source: `backend/tools/seed_smoke_graph.py`
- Document focus: `doc-transformer`
- Query profile: semantic query + inspector node detail + 2-hop style query

## Latest Result Source

- `docs/performance_baseline.latest.json`

## Bottleneck Candidates

- Neo4j query path for evidence-heavy graph traversals.
- Node detail endpoint when relation and citation fan-out is high.
- Ingest parsing/extraction stages when PDF size increases.
