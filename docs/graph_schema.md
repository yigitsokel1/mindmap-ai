# MindMap-AI: Graph Ontology (Data Model)

This document defines the strict schema for the Knowledge Graph. All extraction logic must map to these Nodes and Relationships.

## 1. Nodes (Varlıklar)

### `Paper`
- **Description:** Represents an academic research paper.
- **Properties:**
  - `title` (string): Full title of the paper.
  - `summary` (string): A brief summary or abstract.
  - `year` (integer): Publication year.
  - `doi` (string, optional): Digital Object Identifier.

### `Author`
- **Description:** A person who wrote the paper.
- **Properties:**
  - `name` (string): Full name (Normalized, e.g., "Ashish Vaswani").

### `Institution`
- **Description:** University or Company affiliated with the author.
- **Properties:**
  - `name` (string): e.g., "Google Brain", "MIT".

### `Concept`
- **Description:** Key technical terms, methods, or theories discussed.
- **Properties:**
  - `name` (string): e.g., "Transformer", "Self-Attention", "LSTM".

## 2. Relationships (İlişkiler)

- **(:Author)-[:AUTHORED]->(:Paper)**
  - Indicates who wrote the paper.
  
- **(:Author)-[:AFFILIATED_WITH]->(:Institution)**
  - Connects an author to their organization at the time of writing.

- **(:Paper)-[:MENTIONS]->(:Concept)**
  - Indicates that the paper discusses a specific technical concept significantly.

- **(:Paper)-[:CITES]->(:Paper)**
  - (Advanced) Indicates extraction of references. Paper A cites Paper B.