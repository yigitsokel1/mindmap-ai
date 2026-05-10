# Status — Sprint 27

## Şu an neredeyiz
Sprint 27 tamamlandı. Proje deployment-ready demo durumda: 161 backend + 58 frontend + 6 e2e test, deploy ayakta (Render + Vercel), Launch Checklist tümü ✅.

## Positioning (net)
- Deployed research demo with production-oriented safeguards planned.
- Production-hardening pending: auth policy, stronger rate limits, stricter upload guardrails, storage access isolation.

## Sprint Geçmişi
- Sprint 1-9 ✅ — Temel ingestion, extraction, legacy RAG
- Sprint 10-18 ✅ — Semantic graph, query pipeline, legacy quarantine
- Sprint 19 ✅ — Canonical linking (CanonicalEntity, EntityLinker, CanonicalWriter)
- Sprint 20 ✅ — Compatibility temizliği
- Sprint 21 ✅ — Evidence clustering, InsightBuilder, QuestionInterpreter
- Sprint 22 ✅ — Product readiness review, UI iyileştirme
- Sprint 23 ✅ — Schema sync, dead code temizliği, UI refactor, testler yeşil, eval fix
- Sprint 24 ✅ — Extraction pipeline testleri, hallucination guard, demo path doğrulandı (uncommitted)
- Sprint 25 ✅ — Production deploy (Render + Vercel), CORS env var, PDF 404 fix
- Sprint 26 ✅ — PDF metin highlight (react-pdf), CitationChip, genişletilmiş test suite (161+58+6)
- Sprint 27 ✅ — Deploy review, CORS hardening, InsightBuilder fix (%0→%89), docs temizliği

## Sprint 25 — Görevler
- [x] Sprint 24 uncommitted iş commit'le (kullanıcı tarafından tamamlandı)
- [x] CORS `allow_origins` env var'dan oku — `ALLOWED_ORIGINS` ile yapılandırılabilir hale getir
- [x] `NEXT_PUBLIC_API_URL` `.env.production` ile ayarla
- [x] `npm run build` çalıştır, hata varsa düzelt
- [x] Neo4j AuraDB free tier için production env şablonu eklendi (`backend/.env.production.example`)
- [x] Production Neo4j'e seed data çalıştır (`seed_smoke_graph.py`)
- [x] Backend deploy (Render) — production backend ayakta
- [x] Frontend deploy (Vercel) — `https://frontend-kappa-rosy-63.vercel.app`
- [x] Deploy sonrası demo path doğrula (production URL üzerinden)
- [x] PDF static 404 düzeltmesi: `/static` mount path `backend/uploaded_docs` ile hizalandı

## Sprint 26 — Görevler
- [x] Staged değişiklikleri commit et (PDF 404 fix, FileLibrary fallback name)
- [x] PDFHighlightViewer bileşeni (react-pdf v9) — text layer + keyword highlight
- [x] Inspector: iframe → PDFHighlightViewer, snippet store'dan geliyor
- [x] CommandCenter: evidence.snippet → openPDFViewer'a iletildi
- [x] CitationChip bileşeni citations listesinde kullanılıyor
- [x] `frontend/app/legacy/` boş klasör silindi

## Sprint 27 — Görevler
- [x] Sprint 26 çıktıları commit edildi (15 dosya, 1808 ekleme)
- [x] CORS allow_methods ve allow_headers kısıtlandı (`main.py`)
- [x] `/api/extract` → router'da kasıtlı dışarıda (LLM maliyet güvencesi), architecture.md'de belgelendi
- [x] InsightBuilder fix: EvidenceClusterer cluster key düzeltildi, eval fixtures zenginleştirildi → insight presence %0→%89
- [x] 6 stale docs dosyası silindi
- [x] README portfolyo için güncellendi

## Backlog (Sprint 28+ adayları)
- Semantic eval canonical link precision %48 → iyileştirme
- Semantic eval citation false positive (6 case)
- Auth (API key veya JWT) — production-hardening
- Rate limiting — production-hardening
- Security headers (HSTS, CSP) — production-hardening
- Static PDF serving hardening (signed URL + user isolation) — production-hardening

## Launch Checklist Durumu
- [x] `poetry run pytest backend/tests` — 161 passed (2026-05-10)
- [x] `cd frontend && npm test` — 58 passed (2026-05-10)
- [x] `run_semantic_eval.py` — intent 100%, hallucination 0% (2026-05-10)
- [x] `npm run test:e2e` — 6 passed (2026-05-10)
- [x] Demo path çalışıyor (localhost, 2026-04-27)
- [x] Production deploy ayakta — Sprint 25
- [x] Demo path production URL'de çalışıyor — Sprint 25
