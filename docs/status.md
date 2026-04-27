# Status — Sprint 25

## Şu an neredeyiz
Sprint 24 tamamlandı. Sprint 25 hedefi: portfolio deployment — CORS fix, env config, Neo4j AuraDB, production build, deploy.

## Sprint Geçmişi
- Sprint 1-9 ✅ — Temel ingestion, extraction, legacy RAG
- Sprint 10-18 ✅ — Semantic graph, query pipeline, legacy quarantine
- Sprint 19 ✅ — Canonical linking (CanonicalEntity, EntityLinker, CanonicalWriter)
- Sprint 20 ✅ — Compatibility temizliği
- Sprint 21 ✅ — Evidence clustering, InsightBuilder, QuestionInterpreter
- Sprint 22 ✅ — Product readiness review, UI iyileştirme
- Sprint 23 ✅ — Schema sync, dead code temizliği, UI refactor, testler yeşil, eval fix
- Sprint 24 ✅ — Extraction pipeline testleri, hallucination guard, demo path doğrulandı (uncommitted)

## Sprint 25 — Görevler
- [x] Sprint 24 uncommitted iş commit'le (kullanıcı tarafından tamamlandı)
- [x] CORS `allow_origins` env var'dan oku — `ALLOWED_ORIGINS` ile yapılandırılabilir hale getir
- [x] `NEXT_PUBLIC_API_URL` `.env.production` ile ayarla
- [x] `npm run build` çalıştır, hata varsa düzelt
- [x] Neo4j AuraDB free tier için production env şablonu eklendi (`backend/.env.production.example`)
- [x] Production Neo4j'e seed data çalıştır (`seed_smoke_graph.py`)
- [ ] Backend deploy (Render) — mevcut `mindmap-ai-backend.onrender.com` endpoint'i FastAPI route döndürmüyor (`/` ve `/api/*` 404)
- [x] Frontend deploy (Vercel) — `https://frontend-kappa-rosy-63.vercel.app`
- [ ] Deploy sonrası demo path doğrula (production URL üzerinden) — backend route sorunu nedeniyle bloklu

## Backlog (Sprint 26+ adayları)
- SemanticGraphViewer + FileLibrary upload testleri
- Semantic eval insight correctness %0 — InsightBuilder fixture doğrulaması
- Semantic eval citation false positive (6 case)
- `frontend/app/legacy/` klasörü boş, silinebilir

## Launch Checklist Durumu
- [x] `poetry run pytest backend/tests` — 93 passed (2026-04-27)
- [x] `run_semantic_eval.py` — intent 100%, evidence 100%, hallucination 0% (2026-04-27)
- [x] `npm run test:e2e` — 6 passed (2026-04-27)
- [x] Demo path çalışıyor (localhost, 2026-04-27)
- [ ] Production deploy ayakta — Sprint 25 (frontend ayakta, backend route sorunu var)
- [ ] Demo path production URL'de çalışıyor — Sprint 25 (backend blokajı)
