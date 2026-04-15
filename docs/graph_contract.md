# Graph Contract (Canonical)

This is the single source of truth for core graph traversal contracts used by ingestion, graph writing, and semantic query flows.

## Canonical Structural-Provenance Chain

`Entity -> RelationInstance -> Evidence -> Passage -> Section -> Document`

## Canonical Citation Chain

`Passage -> InlineCitation -> ReferenceEntry`

## Required Relationship Directions

- `(:Entity)-[:OUT_REL]->(:RelationInstance)`
- `(:RelationInstance)-[:TO]->(:Entity)`
- `(:Evidence)-[:SUPPORTS]->(:RelationInstance)`
- `(:Evidence)-[:FROM_PASSAGE]->(:Passage)`
- `(:Document)-[:HAS_SECTION]->(:Section)`
- `(:Section)-[:HAS_PASSAGE]->(:Passage)`
- `(:Passage)-[:HAS_INLINE_CITATION]->(:InlineCitation)`
- `(:InlineCitation)-[:REFERS_TO]->(:ReferenceEntry)`

## Notes

- This contract defines traversal correctness for runtime logic.
- If other documentation conflicts with this file, this file takes precedence.
