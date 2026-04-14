# Frontend Audit — Sprint 9

This audit classifies the current frontend against the semantic graph migration target.

## Component Classification

### Rewrite (semantic-first)

- `frontend/app/components/GraphViewer3D.tsx`
  - Uses legacy `nodes + links` graph shape.
  - Hardcodes `Document` / `Chunk` assumptions in rendering and camera logic.
  - Contains high maintenance animation complexity not aligned with semantic clarity goals.
- `frontend/app/components/FileLibrary.tsx`
  - Derives document list from graph nodes using legacy-style label assumptions.
  - Should become a semantic filter and document-context controller.

### Refactor (salvageable)

- `frontend/app/components/CommandCenter.tsx`
  - Chat path can stay (migration mode), but panel must own semantic graph controls.
  - Needs graph preset and filter UI wiring.
- `frontend/app/components/Inspector.tsx`
  - Existing right panel shell is reusable.
  - Needs node-context mode (passage/evidence/citation/entity details).
- `frontend/app/store/useAppStore.ts`
  - Store structure is valid but too thin for semantic graph state.
  - Needs document, preset, filter, and selected node context fields.
- `frontend/app/components/StatusBar.tsx`
  - UI is reusable; can remain simple health indicator.

### Keep

- `frontend/app/page.tsx`
  - Layout composition remains valid.
  - Needs only graph viewer import swap to semantic-first component.

## Missing or Insufficient Shared Frontend Contracts

- `frontend/app/lib/types.ts`
  - Missing semantic response contracts (`nodes`, `edges`, `meta`).
  - Missing semantic node type union, graph presets, and filter types.
- `frontend/app/lib/constants.ts`
  - Missing semantic preset definitions.
  - Missing endpoint distinction for semantic graph usage and filter defaults.
- Missing API access abstraction
  - Add `frontend/app/lib/api.ts` with `fetchSemanticGraph(params)`.
  - Components should stop building URL/query logic inline.

## Migration Decisions

- Build a new semantic-first viewer component:
  - `frontend/app/components/SemanticGraphViewer.tsx`
- Move active path off legacy assumptions:
  - `page.tsx` should render `SemanticGraphViewer`.
- Preserve chat continuity:
  - Keep current chat API behavior and mark it as legacy mode in UI.
- Establish inspector graph-link minimums:
  - Passage -> open page
  - Evidence -> open linked page/passage context
  - InlineCitation/ReferenceEntry -> show reference details
  - Semantic entity -> show node details + related evidence/links list
