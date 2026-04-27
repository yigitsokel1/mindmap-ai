# Status — Sprint 23 (Kapanış çalışması)

## Şu an neredeyiz
Sprint 23 Phase 2: schema senkronu, test yeşillendirme, launch checklist kapatma.
Sprint 23 Phase 1 uncommitted iş hazır — schema sync + test + commit aşamasında.

## Sprint Geçmişi
- Sprint 1-9 ✅ — Temel ingestion, extraction, legacy RAG
- Sprint 10-18 ✅ — Semantic graph, query pipeline, legacy quarantine
- Sprint 19 ✅ — Canonical linking (CanonicalEntity, EntityLinker, CanonicalWriter)
- Sprint 20 ✅ — Compatibility temizliği (compatibility_delete_list_sprint20.md)
- Sprint 21 ✅ — Evidence clustering, InsightBuilder, QuestionInterpreter
- Sprint 22 ✅ — Product readiness review, UI iyileştirme
- Sprint 23 🔄 — Phase 1 (docs + schema + UI refactor) uncommitted, Phase 2 kapatma aşamasında

## Sprint 23 Phase 1 — Tamamlanan (uncommitted)
- ✅ `docs/graph_storage_model.md` reified pattern'e göre yeniden yazıldı
- ✅ `docs/ontology_v1.md` CanonicalEntity tanımı eklendi
- ✅ `docs/frontend_audit.md` silindi
- ✅ `docs/deprecated/` temizlendi
- ✅ Backend: `NodeDetail.metadata` + `SemanticEvidenceItem.cluster_key` alanları eklendi
- ✅ Frontend: CommandCenter / Inspector / SemanticGraphViewer yeniden yazıldı
- ✅ `manual_acceptance_checklist.md` Sprint 23 Phase 1 pack ile güncellendi

## Sprint 23 Phase 2 — Bu sprint görevleri
- [x] Frontend schema senkronu: `NodeDetail.metadata` + `SemanticEvidenceItem.cluster_key` tiplere eklendi, Inspector + CommandCenter güncellendi
- [x] Dead code temizliği: `API_ENDPOINTS.DOCUMENTS` kaldırıldı, `GraphViewer3D.tsx` + `ChatBubble.tsx` silindi
- [ ] `poetry run pytest backend/tests` ve `npm test` + `npm run test:e2e` yeşil
- [x] `run_semantic_eval.py` — QuestionInterpreter intent fix uygulandı (5 hata düzeltildi, 19/19 lokal), yeniden çalıştırılacak
- [x] `docs/system_overview.md` Sprint 19-22 değişiklikleriyle güncellendi
- [ ] Sprint 23 uncommitted iş parçalı commit'lere ayrılıp commit'lensin (kullanıcı onayıyla)

## Backlog (Sprint 24 adayları)
- Extraction pipeline unit testleri (llm_extractor, pipeline, semantic_ingestion_service) — yüksek risk
- answer_composer + question_interpreter unit testleri — orta risk
- SemanticGraphViewer + FileLibrary upload testleri
- Demo path manuel tam doğrulama (`docs/demo_path.md`)
- Semantic eval hallucination rate %100 — `should_not_answer` guard eksik
- Semantic eval insight correctness %0 — InsightBuilder fixture doğrulaması eksik
- Semantic eval citation false positive (6 case) — citation filter agresif

## Kritik Açık Sorunlar (Audit bulgularından, güncel)

### KRITIK
- [x] `docs/graph_storage_model.md` reified pattern (Phase 1'de kapandı)
- [x] `docs/ontology_v1.md` CanonicalEntity (Phase 1'de kapandı)
- [x] Frontend schema mismatch: `metadata` + `cluster_key` tiplere eklendi, Inspector + CommandCenter güncellendi (Phase 2)

### DIKKAT
- [x] `docs/system_overview.md` güncellendi (Phase 2)
- [ ] Extraction pipeline unit test eksik (backlog → Sprint 24)
- [x] `API_ENDPOINTS.DOCUMENTS` dead constant kaldırıldı (Phase 2)
- [x] `docs/frontend_audit.md` silindi (Phase 1)
- [x] `frontend/app/legacy/GraphViewer3D.tsx` + `ChatBubble.tsx` silindi (Phase 2)

### SCHEMA UYUMSUZLUKLARI
- [x] `NodeDetail.metadata` frontend'e eklendi (Phase 2)
- [x] `evidence[].cluster_key` frontend'e eklendi (Phase 2)
- [x] `nodes[].name` senkron — tip uyumlu

## Neyin Test Edilmediği (Sprint 24 kapsamı)
- llm_extractor.py — YOK (yüksek risk)
- extraction/pipeline.py — YOK (yüksek risk)
- semantic_ingestion_service.py — YOK (yüksek risk)
- answer_composer.py — YOK (orta risk)
- question_interpreter.py — YOK (orta risk)
- SemanticGraphViewer.tsx — YOK
- FileLibrary.tsx upload flow — YOK

## Launch Checklist Durumu
- [ ] `poetry run pytest backend/tests` — çalıştırılmadı
- [x] `run_semantic_eval.py` — intent 100%, evidence 100% (2026-04-27)
- [ ] `npm run test:smoke` — seeded backend gerekli — çalıştırılmadı
- [ ] Demo path çalışıyor (`docs/demo_path.md`) — Sprint 24 manuel
