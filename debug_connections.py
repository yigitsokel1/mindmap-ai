from backend.app.core.db import Neo4jDatabase
from dotenv import load_dotenv

load_dotenv()

db = Neo4jDatabase()
db.connect()

def check_neighbors(keyword):
    print(f"\n🔎 '{keyword}' için komşular aranıyor...")
    with db.driver.session() as session:
        # O kelimeyi içeren düğümleri ve onlara bağlı olan HER ŞEYİ getir
        result = session.run("""
            MATCH (n:Concept)-[r]-(neighbor)
            WHERE toLower(n.id) CONTAINS toLower($keyword)
            RETURN n.id as Merkez, type(r) as Iliski, neighbor.id as Komsu
            LIMIT 20
        """, keyword=keyword)
        
        data = list(result)
        if not data:
            print(f"❌ '{keyword}' içeren düğümlerin HİÇBİR İLİŞKİSİ YOK (Yalnız kovboy).")
        else:
            for record in data:
                print(f"🔗 {record['Merkez']} --[{record['Iliski']}]--> {record['Komsu']}")

print("--- BAĞLANTI ANALİZİ BAŞLIYOR ---")
check_neighbors("Attention")
check_neighbors("Recurrent")
print("\n--------------------------------")
db.close()