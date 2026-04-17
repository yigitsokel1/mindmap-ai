# Acceptance Real Pack

This folder contains a launch-readiness acceptance pack that mirrors real-world usage more closely than synthetic fixtures.

Contents:

- `documents.json`: 3-5 real paper metadata records with stable IDs.
- `cases.json`: reviewer-facing query examples and manual expectations.
- `expected_citations.json`: citation and provenance expectations per case.

Usage:

```bash
poetry run python backend/tools/run_semantic_eval.py --profile acceptance_real
```

Notes:

- `source_url` and `checksum_sha256` are tracked for reproducibility.
- Acceptance checks are deterministic because IDs, expectations, and matching mode are fixed in versioned JSON.
