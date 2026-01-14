from backend.app.core.db import Neo4jDatabase
from dotenv import load_dotenv
import os

load_dotenv()

db = Neo4jDatabase()
db.connect()

print("🔎 Veritabanı Röntgeni Çekiliyor...")
with db.driver.session() as session:
    # İçinde 'Attention' veya 'Recurrent' geçen her şeyi getir
    result = session.run("""
        MATCH (n:Concept) 
        WHERE toLower(n.id) CONTAINS 'attention' OR toLower(n.id) CONTAINS 'recurrent'
        RETURN n.id as Name, labels(n) as Label
    """)
    print("-" * 30)
    records = list(result)
    if records:
        for record in records:
            print(f"📦 Bulunan Düğüm: {record['Name']}")
    else:
        print("❌ Hiçbir Concept node'u bulunamadı.")
    print("-" * 30)

db.close()