"""Script to check node properties in Neo4j database."""

from backend.app.core.db import Neo4jDatabase
from dotenv import load_dotenv
import json

load_dotenv()

db = Neo4jDatabase()
db.connect()

print("🔍 Checking node properties in Neo4j...\n")

# Check Paper nodes
print("=" * 60)
print("PAPER NODES:")
print("=" * 60)
records, _, _ = db.driver.execute_query(
    "MATCH (n:Paper) RETURN n LIMIT 5",
    database_="neo4j"
)

if records:
    for i, record in enumerate(records, 1):
        node = record["n"]
        props = dict(node.items())
        print(f"\nPaper {i}:")
        print(f"  Properties: {list(props.keys())}")
        print(f"  Values: {json.dumps(props, indent=4, default=str)}")
else:
    print("No Paper nodes found")

# Check Concept nodes
print("\n" + "=" * 60)
print("CONCEPT NODES:")
print("=" * 60)
records, _, _ = db.driver.execute_query(
    "MATCH (n:Concept) RETURN n LIMIT 5",
    database_="neo4j"
)

if records:
    for i, record in enumerate(records, 1):
        node = record["n"]
        props = dict(node.items())
        print(f"\nConcept {i}:")
        print(f"  Properties: {list(props.keys())}")
        print(f"  Values: {json.dumps(props, indent=4, default=str)}")
else:
    print("No Concept nodes found")

# Check Author nodes
print("\n" + "=" * 60)
print("AUTHOR NODES:")
print("=" * 60)
records, _, _ = db.driver.execute_query(
    "MATCH (n:Author) RETURN n LIMIT 5",
    database_="neo4j"
)

if records:
    for i, record in enumerate(records, 1):
        node = record["n"]
        props = dict(node.items())
        print(f"\nAuthor {i}:")
        print(f"  Properties: {list(props.keys())}")
        print(f"  Values: {json.dumps(props, indent=4, default=str)}")
else:
    print("No Author nodes found")

db.close()
