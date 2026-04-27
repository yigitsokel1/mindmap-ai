# Test Sonuçları

Her sprint sonunda çalıştırılan test sonuçları buraya kaydedilir.
Yeni sonuç eklendiğinde en üste ekle, eskiler altta kalsın.

---

## Sprint 25 Deployment Run

**Tarih:** 2026-04-27
**Durum:** Kısmi başarılı — frontend production deploy hazır, backend production route doğrulaması başarısız

### Frontend Production Build
```
cd frontend && npm run build
```
Sonuç: PASS (Next.js production build başarılı)

### Production Seed
```
poetry run python backend/tools/seed_smoke_graph.py
```
Sonuç: PASS (`Seed complete. SMOKE_DOCUMENT_ID=doc-transformer`)

### Frontend Deploy (Vercel)
```
cd frontend && vercel --prod --yes
```
Sonuç: PASS (`https://frontend-kappa-rosy-63.vercel.app`)

### Backend URL Smoke
```
GET https://mindmap-ai-backend.onrender.com/
GET https://mindmap-ai-backend.onrender.com/api/query/semantic
```
Sonuç: FAIL (her iki endpoint `404`, FastAPI health/route doğrulaması sağlanmadı)

## Sprint 24 Re-run

**Tarih:** 2026-04-27
**Durum:** Yeniden çalıştırma başarılı (backend + semantic eval + e2e smoke)

### Backend
```
poetry run pytest backend/tests -q
```
Sonuç: PASS (`93 passed`)

### Semantic Eval (semantic_query profili)
```
poetry run python backend/tools/run_semantic_eval.py --profile semantic_query
```
Sonuç:
- Hallucination rate: `0.00% (0/3)`
- Intent accuracy: `100.00%`
- Citation presence: `94.74%`

### E2E / Smoke
```
cd frontend && npm run test:e2e
```
Sonuç: PASS (`6 passed`)

## Sprint 24

**Tarih:** 2026-04-27
**Durum:** Backend testleri ve should_not_answer guard doğrulaması başarılı

### Backend
```
poetry run pytest backend/tests
```
Sonuç: PASS (`93 passed`)

### Semantic Eval (Sprint 24 odak)
```
poetry run python backend/tools/run_semantic_eval.py --profile semantic_query
```
Sonuç:
- Hallucination rate: `0.00% (0/3)` (`should_not_answer` case'leri no-answer)

## Sprint 23 Phase 2

**Tarih:** 2026-04-27
**Durum:** Kısmi başarılı — testler yeşil, semantic eval eşik altı

### Backend
```
poetry run pytest backend/tests
```
Sonuç: PASS (`76 passed`)

### Frontend
```
cd frontend && npm test
```
Sonuç: PASS (`4 passed`)

### E2E / Smoke
```
cd frontend && npm run test:e2e
```
Sonuç: PASS (`6 passed`)

### Semantic Eval
```
poetry run python backend/tools/run_semantic_eval.py
```
**Tarih:** 2026-04-27
**Sonuç:** Launch checklist kriterleri karşılandı

| Metrik | Sonuç | Hedef | Durum |
|--------|-------|-------|-------|
| Intent accuracy | 100.00% | ≥ 80% | ✅ |
| Evidence presence | 100.00% | ≥ 90% | ✅ |
| Citation presence | 78.95% | — | — |
| Section coverage | 100.00% | — | — |
| Keyword hit ratio | 73.68% | — | — |
| Canonical link precision | 48.68% | — | — |
| Canonical entity reuse | 100.00% | — | — |
| Cross-doc hit presence | 84.21% | — | — |
| Insight presence rate | 84.21% | — | — |
| Insight correctness | 0.00% | — | ⚠️ backlog |
| Hallucination rate | 100.00% | — | ⚠️ backlog |
| False positive rate | 100.00% | — | ⚠️ backlog |
| Cluster quality score | 23.70% | — | — |

**Açık sorunlar (Sprint 24 backlog):**
- Hallucination rate %100 — `should_not_answer` guard yok
- Insight correctness %0 — InsightBuilder fixture'da doğrulama eksik
- Citation false positive — `expected=False` iken citation dönüyor (6 case)
