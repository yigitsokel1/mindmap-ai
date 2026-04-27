# MindMap-AI: Graph Storage Model

This document defines how the V1 ontology maps to Neo4j storage — node labels, properties, relationships, constraints, indexes, and the provenance storage pattern.

Source of truth for traversal contracts: `docs/graph_contract.md`.

**Version:** 1.0
**Status:** Active
**Depends on:** `ontology_v1.md`, `extraction_contract.md`
**Database:** Neo4j 5.x+

---

## Storage Principles

1. **MERGE for semantic entities** — Use `MERGE` on `canonical_name` to prevent duplicate nodes. `CREATE` only for structural nodes (Document, Section, Passage) and Evidence nodes (always unique).

2. **Evidence as nodes via reified relations** — Provenance metadata lives in `Evidence` nodes linked to `RelationInstance` via `SUPPORTS` and to `Passage` via `FROM_PASSAGE`.

3. **Structural edges are propertyless** (except `ordinal`) — No provenance needed for `HAS_SECTION` / `HAS_PASSAGE`.

4. **All nodes have `uid`** — UUID primary key, unique-constrained.

5. **Indexes on `canonical_name`** — Every semantic node type has an index on `canonical_name` for fast MERGE and lookup.

---

## Node Label → Property Mapping

### Structural Nodes

#### `:Document`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `title` | String | — | Paper title |
| `file_hash` | String | UNIQUE | MD5 hash for dedup |
| `file_name` | String | — | Original filename |
| `saved_file_name` | String | — | Filename in uploaded_docs/ |
| `abstract` | String | — | Paper abstract |
| `year` | Integer | — | Publication year |
| `doi` | String | — | Digital Object Identifier |
| `created_at` | DateTime | — | Ingestion timestamp |

#### `:Section`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `title` | String | — | Section heading |
| `ordinal` | Integer | — | Position in document (0-indexed) |
| `level` | Integer | — | Heading depth (1 = top-level) |

#### `:Passage`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `text` | String | — | Raw passage text |
| `page` | Integer | — | PDF page number (0-indexed) |
| `char_offset_start` | Integer | — | Character offset start |
| `char_offset_end` | Integer | — | Character offset end |
| `embedding` | List[Float] | — | Optional vector (1536-dim) |
| `extraction_status` | String | — | "pending" / "completed" / "failed" / "empty" |

#### `:ReferenceEntry`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `raw_text` | String | — | Full reference text |
| `order` | Integer | — | Position in reference list (0-indexed) |
| `year` | Integer | — | Extracted publication year |
| `title_guess` | String | — | Heuristic title extraction |
| `authors_guess` | List[String] | — | Heuristic author surnames |
| `citation_key_numeric` | Integer | — | Numeric key used by inline citations |
| `citation_key_author_year` | List[String] | — | Author-year keys for approximate matching |
| `created_at` | DateTime | — | Ingestion timestamp |

#### `:InlineCitation`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `raw_text` | String | — | Raw citation marker from passage |
| `citation_style` | String | — | `numeric_bracket` or `author_year` |
| `start_char` | Integer | — | Passage-local offset start |
| `end_char` | Integer | — | Passage-local offset end |
| `page_number` | Integer | — | Source page number |
| `reference_keys` | List[String] | — | Parsed numeric keys |
| `reference_labels` | List[String] | — | Parsed author-year labels |
| `created_at` | DateTime | — | Ingestion timestamp |

### Semantic Nodes

#### `:Author`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `canonical_name` | String | INDEX | Normalized full name |
| `surface_forms` | List[String] | — | Observed name variants |

#### `:Institution`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `canonical_name` | String | INDEX | Normalized name |
| `surface_forms` | List[String] | — | Observed variants |
| `type` | String | — | "university" / "company" / "lab" / "government" |

#### `:Concept`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `canonical_name` | String | INDEX | Normalized name |
| `surface_forms` | List[String] | — | Observed variants |
| `definition` | String | — | Extracted definition |

#### `:Method`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `canonical_name` | String | INDEX | Normalized name |
| `surface_forms` | List[String] | — | Observed variants |
| `description` | String | — | Brief description |

#### `:Dataset`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `canonical_name` | String | INDEX | Normalized name |
| `surface_forms` | List[String] | — | Observed variants |
| `domain` | String | — | Domain area |

#### `:Metric`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `canonical_name` | String | INDEX | Normalized name |
| `surface_forms` | List[String] | — | Observed variants |

#### `:Task`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `canonical_name` | String | INDEX | Normalized name |
| `surface_forms` | List[String] | — | Observed variants |

### Provenance Node

#### `:Evidence`

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `passage_uid` | String | INDEX | FK to Passage.uid |
| `document_uid` | String | INDEX | FK to Document.uid |
| `confidence` | Float | — | 0.0 – 1.0 |
| `extraction_method` | String | — | e.g., "llm_gpt4o" |
| `extracted_at` | DateTime | — | Extraction timestamp |
| `surface_text` | String | — | Supporting text span |
| `citation_count` | Integer | — | Number of inline citations in source passage |
| `citation_labels` | List[String] | — | Citation labels detected in source passage |

---

## Relationship Type → Property Mapping

### Structural Relationships

| Type | Source → Target | Properties | Notes |
|------|----------------|------------|-------|
| `HAS_SECTION` | Document → Section | `ordinal: Integer` | No provenance |
| `HAS_PASSAGE` | Section → Passage | `ordinal: Integer` | No provenance |
| `HAS_REFERENCE` | Document → ReferenceEntry | `order: Integer` | No provenance |
| `HAS_INLINE_CITATION` | Passage → InlineCitation | — | Structural citation anchor |
| `REFERS_TO` | InlineCitation → ReferenceEntry | `confidence: Float` | Link from mention to parsed bibliography entry |

### Reified Semantic Relationship Pattern (`:RelationInstance`)

Semantic relations are represented as nodes (`:RelationInstance`) rather than direct typed edges between entities.
This follows the canonical chain in `docs/graph_contract.md`:

- `(:Entity)-[:OUT_REL]->(:RelationInstance)`
- `(:RelationInstance)-[:TO]->(:Entity)`
- `(:Evidence)-[:SUPPORTS]->(:RelationInstance)`

`RelationInstance` stores relation semantics as node properties.

| Type | Source → Target | Properties | Notes |
|------|----------------|------------|-------|
| `OUT_REL` | Entity → RelationInstance | — | Connects source entity to reified relation instance |
| `TO` | RelationInstance → Entity | — | Connects relation instance to target entity |
| `SUPPORTS` | Evidence → RelationInstance | — | Provenance support for this relation assertion |
| `FROM_PASSAGE` | Evidence → Passage | — | Where the evidence was found |

`RelationInstance` property shape:

| Property | Neo4j Type | Constraint | Description |
|----------|-----------|------------|-------------|
| `uid` | String | UNIQUE | Primary key (UUID) |
| `type` | String | INDEX | Canonical relation type (e.g., `WROTE`, `USES`) |
| `confidence` | Float | — | Optional aggregate confidence for the asserted relation |
| `created_at` | DateTime | — | Relation instance creation timestamp |

---

## Constraint & Index Definitions

Run these on database initialization (via `schema_init.py` at startup).

```cypher
// ============================================================
// UNIQUENESS CONSTRAINTS
// ============================================================

CREATE CONSTRAINT doc_uid IF NOT EXISTS
  FOR (d:Document) REQUIRE d.uid IS UNIQUE;

CREATE CONSTRAINT doc_hash IF NOT EXISTS
  FOR (d:Document) REQUIRE d.file_hash IS UNIQUE;

CREATE CONSTRAINT section_uid IF NOT EXISTS
  FOR (s:Section) REQUIRE s.uid IS UNIQUE;

CREATE CONSTRAINT passage_uid IF NOT EXISTS
  FOR (p:Passage) REQUIRE p.uid IS UNIQUE;

CREATE CONSTRAINT author_uid IF NOT EXISTS
  FOR (a:Author) REQUIRE a.uid IS UNIQUE;

CREATE CONSTRAINT institution_uid IF NOT EXISTS
  FOR (i:Institution) REQUIRE i.uid IS UNIQUE;

CREATE CONSTRAINT concept_uid IF NOT EXISTS
  FOR (c:Concept) REQUIRE c.uid IS UNIQUE;

CREATE CONSTRAINT method_uid IF NOT EXISTS
  FOR (m:Method) REQUIRE m.uid IS UNIQUE;

CREATE CONSTRAINT dataset_uid IF NOT EXISTS
  FOR (ds:Dataset) REQUIRE ds.uid IS UNIQUE;

CREATE CONSTRAINT metric_uid IF NOT EXISTS
  FOR (mt:Metric) REQUIRE mt.uid IS UNIQUE;

CREATE CONSTRAINT task_uid IF NOT EXISTS
  FOR (t:Task) REQUIRE t.uid IS UNIQUE;

CREATE CONSTRAINT evidence_uid IF NOT EXISTS
  FOR (e:Evidence) REQUIRE e.uid IS UNIQUE;

CREATE CONSTRAINT reference_uid IF NOT EXISTS
  FOR (r:ReferenceEntry) REQUIRE r.uid IS UNIQUE;

CREATE CONSTRAINT inline_citation_uid IF NOT EXISTS
  FOR (c:InlineCitation) REQUIRE c.uid IS UNIQUE;

// ============================================================
// LOOKUP INDEXES (canonical_name for MERGE performance)
// ============================================================

CREATE INDEX author_name IF NOT EXISTS
  FOR (a:Author) ON (a.canonical_name);

CREATE INDEX institution_name IF NOT EXISTS
  FOR (i:Institution) ON (i.canonical_name);

CREATE INDEX concept_name IF NOT EXISTS
  FOR (c:Concept) ON (c.canonical_name);

CREATE INDEX method_name IF NOT EXISTS
  FOR (m:Method) ON (m.canonical_name);

CREATE INDEX dataset_name IF NOT EXISTS
  FOR (ds:Dataset) ON (ds.canonical_name);

CREATE INDEX metric_name IF NOT EXISTS
  FOR (mt:Metric) ON (mt.canonical_name);

CREATE INDEX task_name IF NOT EXISTS
  FOR (t:Task) ON (t.canonical_name);

// ============================================================
// PROVENANCE INDEXES
// ============================================================

CREATE INDEX evidence_passage IF NOT EXISTS
  FOR (e:Evidence) ON (e.passage_uid);

CREATE INDEX evidence_document IF NOT EXISTS
  FOR (e:Evidence) ON (e.document_uid);

// ============================================================
// OPTIONAL: VECTOR INDEX (for RAG fallback on Passage embeddings)
// ============================================================
// Uncomment when RAG fallback is enabled:
//
// CREATE VECTOR INDEX passage_embedding IF NOT EXISTS
//   FOR (p:Passage) ON (p.embedding)
//   OPTIONS {
//     indexConfig: {
//       `vector.dimensions`: 1536,
//       `vector.similarity_function`: 'cosine'
//     }
//   };
```

---

## Provenance Storage Pattern

### Single Evidence

When an entity/relation is extracted from one passage:

```cypher
// 1. Create or merge the semantic entity
MERGE (m:Method {canonical_name: "Transformer"})
  ON CREATE SET m.uid = $method_uid, m.surface_forms = [$surface_form]
  ON MATCH SET m.surface_forms =
    CASE WHEN NOT $surface_form IN m.surface_forms
         THEN m.surface_forms + $surface_form
         ELSE m.surface_forms END

// 2. Create a reified relation instance between source and target entities
MATCH (d:Document {uid: $doc_uid})
MERGE (ri:RelationInstance {uid: $ri_uid})
  ON CREATE SET ri.type = "INTRODUCES",
                ri.source_uid = d.uid,
                ri.target_uid = m.uid,
                ri.confidence = $confidence,
                ri.created_at = datetime()
  ON MATCH SET ri.confidence = $confidence
MERGE (d)-[:OUT_REL]->(ri)
MERGE (ri)-[:TO]->(m)

// 3. Create the Evidence node
CREATE (e:Evidence {
  uid: $ev_uid,
  passage_uid: $pass_uid,
  document_uid: $doc_uid,
  confidence: $confidence,
  extraction_method: $extraction_method,
  extracted_at: datetime(),
  surface_text: $surface_text
})

// 4. Link evidence to relation instance and passage
MATCH (p:Passage {uid: $pass_uid})
MATCH (ri:RelationInstance {uid: $ri_uid})
CREATE (e)-[:FROM_PASSAGE]->(p)
CREATE (e)-[:SUPPORTS]->(ri)
```

### Multi-Evidence

When the same relation is supported by multiple passages (e.g., "Transformer" is mentioned in sections 1, 3, and 5):

Each passage extraction creates a new Evidence node linked to the same `RelationInstance`:

```cypher
// After second extraction from a different passage
MATCH (d:Document {uid: $doc_uid})-[:OUT_REL]->(ri:RelationInstance {uid: $ri_uid})-[:TO]->(m:Method {canonical_name: "Transformer"})
SET ri.confidence = $new_confidence

CREATE (e:Evidence {
  uid: $new_ev_uid,
  passage_uid: $different_pass_uid,
  document_uid: $doc_uid,
  confidence: $new_confidence,
  extraction_method: $extraction_method,
  extracted_at: datetime(),
  surface_text: $new_surface_text
})
MATCH (p:Passage {uid: $different_pass_uid})
CREATE (e)-[:FROM_PASSAGE]->(p)
CREATE (e)-[:SUPPORTS]->(ri)
```

### Confidence Aggregation

When a relation has multiple Evidence nodes, the effective confidence can be computed:

```cypher
// Aggregate confidence for a relation instance
MATCH (d:Document {uid: $doc_uid})-[:OUT_REL]->(ri:RelationInstance)-[:TO]->(m:Method)
MATCH (e:Evidence)-[:SUPPORTS]->(ri)
WITH m, ri, collect(e.confidence) AS confidences
RETURN m.canonical_name,
       ri.type AS relation_type,
       reduce(max = 0.0, c IN confidences | CASE WHEN c > max THEN c ELSE max END) AS max_confidence,
       reduce(sum = 0.0, c IN confidences | sum + c) / size(confidences) AS avg_confidence,
       size(confidences) AS evidence_count
```

---

## Common Cypher Operations

### 1. Ingest Document Structure

```cypher
// Create document
CREATE (d:Document {
  uid: $doc_uid,
  title: $title,
  file_hash: $file_hash,
  file_name: $file_name,
  saved_file_name: $saved_file_name,
  abstract: $abstract,
  year: $year,
  created_at: datetime()
})

// Batch create sections
UNWIND $sections AS sec
MATCH (d:Document {uid: $doc_uid})
CREATE (s:Section {
  uid: sec.uid,
  title: sec.title,
  ordinal: sec.ordinal,
  level: sec.level
})
CREATE (d)-[:HAS_SECTION {ordinal: sec.ordinal}]->(s)

// Batch create passages
UNWIND $passages AS pass
MATCH (s:Section {uid: pass.section_uid})
CREATE (p:Passage {
  uid: pass.uid,
  text: pass.text,
  page: pass.page,
  char_offset_start: pass.char_offset_start,
  char_offset_end: pass.char_offset_end,
  extraction_status: "pending"
})
CREATE (s)-[:HAS_PASSAGE {ordinal: pass.ordinal}]->(p)
```

### 2. Store Extracted Entities (Batch)

```cypher
UNWIND $entities AS ent
CALL {
  WITH ent
  MERGE (n {canonical_name: ent.name})
    ON CREATE SET
      n.uid = ent.uid,
      n.surface_forms = [ent.surface_form],
      n:` + ent.label + `
    ON MATCH SET
      n.surface_forms =
        CASE WHEN NOT ent.surface_form IN n.surface_forms
             THEN n.surface_forms + ent.surface_form
             ELSE n.surface_forms END
} IN TRANSACTIONS OF 100 ROWS
```

> Note: Dynamic label assignment requires APOC or separate queries per entity type. In practice, use one MERGE query per entity type for type safety.

### 3. Query: All Methods in a Document with Evidence

```cypher
MATCH (d:Document {uid: $doc_uid})-[:OUT_REL]->(ri:RelationInstance {type: "INTRODUCES"})-[:TO]->(m:Method)
MATCH (e:Evidence)-[:SUPPORTS]->(ri)-[:TO]->(m)
MATCH (e)-[:FROM_PASSAGE]->(p:Passage)
RETURN m.canonical_name AS method,
       ri.type AS relation_type,
       m.description AS description,
       e.confidence AS confidence,
       e.surface_text AS evidence,
       p.page AS page
ORDER BY e.confidence DESC
```

### 4. Query: Full Provenance Trace

```cypher
// Trace any reified semantic relation back to its source
MATCH (e:Evidence {uid: $ev_uid})-[:SUPPORTS]->(ri:RelationInstance)
MATCH (src)-[:OUT_REL]->(ri)-[:TO]->(tgt)
MATCH (e)-[:FROM_PASSAGE]->(p:Passage)<-[:HAS_PASSAGE]-(s:Section)<-[:HAS_SECTION]-(d:Document)
RETURN labels(src)[0] AS source_type, src.canonical_name AS source_name,
       ri.type AS relation,
       labels(tgt)[0] AS target_type, tgt.canonical_name AS target_name,
       e.confidence AS confidence,
       e.surface_text AS evidence_text,
       p.page AS page,
       s.title AS section,
       d.title AS document
```

### 5. Query: Graph for Visualization

```cypher
// Fetch all semantic nodes and their reified relationships for rendering
MATCH (n)
WHERE n:Author OR n:Institution OR n:Concept OR n:Method
   OR n:Dataset OR n:Metric OR n:Task OR n:Document
OPTIONAL MATCH (n)-[:OUT_REL]->(ri:RelationInstance)-[:TO]->(m)
RETURN n, ri, m
LIMIT 5000
```

### 6. Query: Documents About a Task

```cypher
MATCH (d:Document)-[:OUT_REL]->(:RelationInstance {type: "ABOUT"})-[:TO]->(t:Task {canonical_name: $task_name})
RETURN d.uid, d.title, d.year
ORDER BY d.year DESC
```

### 7. Query: Entity Neighborhood (1-hop)

```cypher
MATCH (center {canonical_name: $entity_name})
OPTIONAL MATCH (center)-[:OUT_REL]->(ri_out:RelationInstance)-[:TO]->(neighbor_out)
OPTIONAL MATCH (neighbor_in)-[:OUT_REL]->(ri_in:RelationInstance)-[:TO]->(center)
WITH center,
     collect({relation: ri_out.type, neighbor: neighbor_out}) +
     collect({relation: ri_in.type, neighbor: neighbor_in}) AS rows
UNWIND rows AS row
WITH center, row
WHERE row.neighbor IS NOT NULL
RETURN labels(center)[0] AS center_type, center.canonical_name AS center,
       row.relation AS relation,
       labels(row.neighbor)[0] AS neighbor_type,
       COALESCE(row.neighbor.canonical_name, row.neighbor.title) AS neighbor_name
```

### 8. Delete Document and All Related Data

```cypher
// Cascade delete: document -> sections -> passages -> evidence + relation instances
MATCH (d:Document {uid: $doc_uid})

// Delete evidence linked to this document
OPTIONAL MATCH (e:Evidence {document_uid: $doc_uid})
DETACH DELETE e

// Delete passages and sections
OPTIONAL MATCH (d)-[:HAS_SECTION]->(s:Section)-[:HAS_PASSAGE]->(p:Passage)
DETACH DELETE p, s

// Delete document (and its OUT_REL links)
DETACH DELETE d

// Note: Semantic entities (Method, Concept, etc.) are NOT deleted
// because they may be referenced by other documents.
// Orphan cleanup is a separate maintenance operation.
```

---

## Migration from Legacy Schema

The current database has `:Document` and `:Chunk` nodes with `BELONGS_TO` relationships. Migration path:

1. **Do not drop legacy data immediately** — Run new schema constraints alongside old data
2. **Re-ingest documents** through the new pipeline to create Section/Passage/Entity nodes
3. **After verification**, remove old Chunk nodes:

```cypher
// Remove legacy chunk data (after new pipeline is verified)
MATCH (c:Chunk) DETACH DELETE c
```

4. **Drop legacy indexes** if any exist on Chunk properties

---

## Performance Considerations

- **MERGE on canonical_name**: Requires INDEX on `canonical_name` for each semantic label. Without these indexes, MERGE performance degrades linearly with node count.

- **High-support relation fan-in**: For heavily supported facts, many `Evidence` nodes may point to one `RelationInstance`. If support count grows very large, consider archival/partitioning strategies.

- **Passage text storage**: Full passage text is stored in Passage nodes. For very large documents, this can consume significant heap. Consider external text storage (file reference) for documents with 1000+ passages.

- **Vector index**: The optional vector index on `Passage.embedding` uses `cosine` similarity and 1536 dimensions (OpenAI text-embedding-3-small). Enable only when RAG fallback is needed.
