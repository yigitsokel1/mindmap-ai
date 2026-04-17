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

## 8) Sprint 22 Product Polish Checks

- [ ] Verify result panel hierarchy renders in order: Answer -> Key Points -> Insights -> Clustered Evidence -> Citations -> Advanced Reasoning Details.
- [ ] Confirm low-confidence or overflow insights are moved into folded "Additional Insights" and default view stays readable.
- [ ] Validate noisy cases do not overclaim: no cross-document trend from a single weak mention.
- [ ] Confirm insight panel opens with concise product-language helper copy (no heavy technical jargon).
- [ ] Confirm clustered evidence fallback message appears when evidence exists but clustering is empty.
- [ ] Confirm canonical panel appears as second-layer inspector block and does not hide local node summary.
- [ ] Confirm grouped relations and citations remain collapsible/expandable without losing content.
- [ ] Run smoke flow with backend enabled and verify: query -> answer + insights + clustered evidence.
- [ ] Verify inspector smoke flow: summary and canonical panel are visible after entity inspect.
- [ ] Verify citation click opens provenance context and inspector label is set to Citation.
