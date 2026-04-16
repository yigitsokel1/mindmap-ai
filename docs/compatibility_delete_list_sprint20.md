# Compatibility Delete List (Sprint 20 Candidate)

This list tracks legacy shims and compatibility surfaces audited in Sprint 18.5.

## Keep For Now
- `backend/app/api/graph.py` compatibility route `/api/graph` (alias)  
  - **Reason**: may still be called by external clients.
  - **Removal condition**: observed zero traffic during deprecation window.

## Remove When Safe
- `frontend/app/lib/constants.ts` alias constant `API_ENDPOINTS.GRAPH`  
  - **Status**: removed from active frontend constants in Sprint 18.5.
- Legacy type aliases in `frontend/app/lib/types.ts`:
  - `GraphLink = GraphEdge`
  - `GraphData = GraphRenderData`
  - **Action**: remove once no compatibility imports remain.
- `frontend/app/legacy/components/GraphViewer3D.tsx`
  - **Action**: remove when no runtime or test import depends on this legacy component.

## Quarantine Rule
- New features must not add new dependencies on alias routes or legacy components.
- Canonical runtime paths for graph reads remain:
  - `/api/graph/semantic`
  - `/api/graph/node/{id}`
