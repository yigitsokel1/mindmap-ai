# MindMap-AI — AI Context

## Proje
Akademik PDF → Neo4j semantic graph → grounded Q&A.

## Başlamadan önce oku
| Konu | Dosya |
|------|-------|
| Mimari & mevcut durum | `docs/architecture.md` |
| Ne bitti, ne kaldı | `docs/status.md` |
| Çalışma kuralları | `docs/workflow.md` |
| Son test sonuçları | `docs/test_results.md` |

## Kesin kurallar
- `backend/app/legacy/` ve `frontend/app/legacy/` → dokunma
- `docs/deprecated/` → referans alma
- Yeni node/relation tipi → `docs/architecture.md` ontoloji bölümüne bak
- `domain/identity.py` → değiştirme
- `schemas/` → değiştirmeden önce frontend etkisini düşün

## Test komutları
```bash
poetry run pytest backend/tests
poetry run python -m compileall backend/app
poetry run python backend/tools/run_semantic_eval.py
cd frontend && npm test
cd frontend && npm test:e2e
```
