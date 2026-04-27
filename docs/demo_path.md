# Demo Path (Guided Happy Path)

## Goal

Show a complete evidence-backed flow in under 5 minutes.

## Preconditions

- Backend running at `http://127.0.0.1:8000`
- Frontend running at `http://127.0.0.1:3000`
- Seed applied: `poetry run python backend/tools/seed_smoke_graph.py`
- Document ID: `doc-transformer`

## Steps

1. Open app and verify first-run hint text is visible.
2. In Query panel ask:
   - `How is Transformer grounded in this paper?`
3. Show:
   - answer confidence block
   - clustered evidence panel
   - insights panel
4. Expand advanced reasoning and click a matched entity chip.
5. In Inspector, explain:
   - summary
   - canonical panel
   - grouped relations
6. Click a citation item and follow provenance context in Inspector (`Citation`).

## Success Signal

Audience sees one end-to-end loop: question -> grounded answer -> inspect entity -> follow citation provenance.

## Sprint 25 Production Check

- Frontend URL: `https://frontend-kappa-rosy-63.vercel.app`
- Backend URL (configured): `https://mindmap-ai-backend.onrender.com`
- Current status: bloklu. Backend URL FastAPI endpoint'lerini döndürmediği için (`/` ve `/api/*` 404), production demo path henüz doğrulanamadı.
