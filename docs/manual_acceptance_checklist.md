## Sprint 23 - Phase 1 Real Acceptance Pack

- Run `poetry run python backend/tools/run_semantic_eval.py --profile acceptance_real`.
- Verify all cases under `backend/evals/acceptance_real/cases.json` are executed.
- Confirm citation/provenance matches `backend/evals/acceptance_real/expected_citations.json`.
- Spot-check at least 2 cases manually in UI:
  - answer text grounded in evidence snippets
  - citation click leads to provenance context in inspector

### Latest Execution Snapshot (Sprint 23 Phase 2)

- Timestamp: 2026-04-27
- `poetry run pytest backend/tests` -> PASS (`76 passed`)
- `cd frontend && npm test` -> PASS (`4 passed`)
- `cd frontend && npm run test:e2e` -> PASS (`6 passed`)
- `poetry run python backend/tools/run_semantic_eval.py` -> RUN COMPLETED, acceptance thresholds NOT MET
  - Intent accuracy: `73.68%` (target >= `80%`) -> FAIL
  - Evidence presence: `100.00%` (target >= `90%`) -> PASS
  - Citation presence: `78.95%` (target >= `90%`) -> FAIL
  - Insight correctness: `0.00%` -> FAIL
  - Cluster quality score: `23.70%` -> FAIL
  - False positive rate: `100.00%` -> FAIL
  - Hallucination rate: `100.00%` -> FAIL

# Manual Acceptance Checklist

This checklist is the product-level validation flow for each sprint closeout.
Use it after backend tests pass, and record pass/fail notes with timestamps.

## 1) Ingest flow

- [ ] Start backend and frontend with clean logs.
- [ ] Ingest a representative PDF through `POST /api/ingest` (default semantic mode).
- [ ] Verify ingest response includes document identity and success status.
- [ ] Confirm graph contains semantic nodes/edges for the ingested document.

## 2) Provenance chain

- [ ] Pick one extracted relation in graph view.
- [ ] Verify provenance chain exists: `Evidence -> RelationInstance -> Entity context`.
- [ ] Verify evidence links to passage via `FROM_PASSAGE`.
- [ ] Verify passage text/snippet aligns with expected relation statement.

## 3) Citation chain

- [ ] For an evidence-backed relation, verify passage has inline citations.
- [ ] Confirm citation chain exists: `Passage -> InlineCitation -> ReferenceEntry`.
- [ ] Confirm citation label shown in UI/API maps to stored citation data.
- [ ] Confirm reference entry ID is present in semantic query evidence output.

## 4) Graph API filters

- [ ] Call `GET /api/graph/semantic` with `document_id` and verify only target document scope is returned.
- [ ] Validate `node_types` filtering using CSV and repeated query parameter forms.
- [ ] Toggle `include_structural`, `include_evidence`, `include_citations` and verify edge subsets change as expected.
- [ ] Confirm response contract remains `nodes`, `edges`, `meta`.

## 5) Frontend graph behavior

- [ ] Load graph view and confirm data renders without runtime errors.
- [ ] Verify focus/highlight navigation moves camera to expected nodes.
- [ ] Verify filters/presets update graph view deterministically.
- [ ] Confirm no UI regression in graph panel interactions.

## 6) Semantic query behavior

- [ ] Ask an entity-centric question (methods/concepts) and verify grounded relation response.
- [ ] Ask an evidence-centric question and verify evidence snippet and page are present.
- [ ] Ask a citation/reference question and verify citation labels and reference IDs are returned.
- [ ] Run a query with `document_id` and verify results are document-scoped.
- [ ] Run a no-match query and verify clean fallback answer and empty evidence arrays.

## 7) Duplicate stability

- [ ] Re-ingest the same PDF and verify duplicate handling behavior is stable.
- [ ] Re-run the same semantic query and compare evidence ordering/shape consistency.
- [ ] Confirm no unexpected explosive growth in duplicate nodes/edges.
- [ ] Record any drift in confidence, evidence count, or citation count.

## 8) Sprint 1 UX Cleanup Checks

- [ ] Confirm `CommandCenter` runs in Files-first inline layout (no Query/Files tab switching).
- [ ] Confirm `Query Mode` and `Advanced Graph Controls` are removed from production UI.
- [ ] Verify file card primary click applies document filter without auto-opening PDF.
- [ ] Verify file card secondary `Open` action opens PDF and keeps selected document highlighted.
- [ ] Confirm all filter reset actions use consistent `Clear filter` wording.
- [ ] Verify node click opens PDF directly when source document/page exists.
- [ ] Verify node click with no source shows `No source location available` in inspector.
- [ ] Confirm graph view no longer shows debug/bypass developer controls.
- [ ] Run smoke flow with backend enabled and verify: query -> answer + insights + clustered evidence + citations.

## 9) Sprint 1.5 Semantic UX Checks

- [ ] Load two different PDFs and verify each file applies a distinct semantic graph scope.
- [ ] Confirm selected document scope does not produce `No graph for active filter` unless data is truly missing.
- [ ] Verify file card click applies scope only; `Open` action opens PDF without changing the interaction model.
- [ ] Ask a semantic query and verify graph highlight/focus updates from query evidence (not only text answer).
- [ ] Toggle relevant-only focus and verify fallback message appears if focused nodes are absent in current scope.
- [ ] Click citation result and verify both inspector context and graph focus update.
- [ ] Click graph node and verify inspector shows semantic panel fields: name, type, summary, source/snippet when present.
- [ ] Verify inspector shows `Open PDF` when source document exists; otherwise shows `No source location available`.
- [ ] Verify tooltip is contextual (name + type + source hint) and node selection is visually distinct.

## 10) Sprint 2 Semantic Backbone Checks

- [ ] Single PDF scenario: select a document and verify graph/query scope uses canonical `Document.uid`.
- [ ] Single PDF scenario: ask a semantic query and verify response includes `primary_focus_node_id` and `secondary_focus_node_ids`.
- [ ] Single PDF scenario: verify camera first focuses primary node, then keeps secondary support nodes highlighted.
- [ ] Multi PDF unrelated scenario: with one document filter active, verify cross-document edges are hidden unless explicitly `edge_scope=bridged`.
- [ ] Multi PDF related scenario: with one document filter active, verify evidence-backed cross-document edges appear as bridged and visually weaker.
- [ ] Citation navigation: click citation and verify inspector + graph focus stay aligned to the same semantic context.
- [ ] Inspector source fallback: on nodes without direct context source, verify source is derived from node evidences when available.
- [ ] Empty-state regression: verify no-crash behavior when scoped graph is empty and fallback messaging remains clear.
