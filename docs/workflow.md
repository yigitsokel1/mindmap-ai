# Workflow — Çalışma Kuralları

## Her oturum başında
1. docs/status.md oku — nerede olduğunu anla
2. docs/architecture.md oku — neye dokunabileceğini anla
3. docs/test_results.md oku — son test sonuçlarını ve açık hataları gör
4. Sadece o oturumun görevini yap, başka bir şeye genişleme

## Her oturum sonunda
1. Değişen her şeyi docs/status.md'ye yaz
2. Yeni servis/module eklediysen docs/architecture.md'yi güncelle
3. Docs ile kod arasında yeni çelişki yarattıysan işaretle

## "Bitti" kriterleri
Bir görev şu koşullar sağlanmadan bitmez:
- Test geçiyor (ilgili test varsa)
- Docs güncellendi (değişiklik docs'u etkiliyor ise)
- Legacy koda dokunulmadı
- Scope dışına çıkılmadı

## Scope kuralları
- "Bunu da eklesek iyi olur" → HAYIR, status.md'ye backlog olarak yaz
- Legacy klasörüne dokunmak için gerekçe şart
- Yeni node tipi eklemek → önce architecture.md'ye ekle, sonra kodu yaz
- Schema değişikliği → backend + frontend aynı anda güncellenmeli

## Docs öncelik sırası (çelişki olursa)
1. docs/graph_contract.md — en yetkili (graph pattern)
2. docs/architecture.md — mimari
3. docs/ontology_v1.md — entity/relation tipleri
4. docs/extraction_contract.md — extraction I/O
5. Diğer docs — yardımcı

## Silinmesi gereken (temizlik listesi)
- frontend/app/legacy/ — quarantine, silinmeli (Sprint 23 Phase 2'de legacy tsx'ler silindi, klasör boş kaldı)
