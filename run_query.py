"""Legacy retrieval debug script.

This helper runs the current legacy chat retrieval path for diagnostics.
Semantic query chat is pending and not wired here.
"""

import os
from dotenv import load_dotenv
from backend.app.services.legacy.retrieval import GraphRAGService

# .env yükle
load_dotenv()

def main():
    print("🤖 GraphRAG Asistanı Başlatılıyor...")
    
    try:
        service = GraphRAGService()
        
        # Soru: Veritabanında gördüğümüz (Loglardan bildiğimiz) kavramları soralım
        query = "How are 'Attention mechanisms' related to 'Recurrent models'?"
        
        print(f"\n❓ Soru: {query}")
        print("-" * 50)
        
        result = service.answer_question(query)
        
        print("-" * 50)
        print(f"💡 Cevap:\n{result['result']}")
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ Hata: {e}")

if __name__ == "__main__":
    main()