"""Seed deterministic semantic graph data for smoke tests."""

from __future__ import annotations

from backend.app.core.db import Neo4jDatabase


SEED_DOCUMENT_ID = "doc-transformer"


def run_seed() -> None:
    db = Neo4jDatabase()
    if not db.driver:
        db.connect()

    reset_query = """
    MATCH (n)
    WHERE coalesce(n.seed_tag, '') = 'sprint23_smoke'
    DETACH DELETE n
    """
    db.execute_query_with_retry(reset_query)

    create_query = """
    MERGE (d:Document {uid: $document_id})
    SET d.title = 'attention_is_all_you_need.pdf',
        d.file_name = 'attention_is_all_you_need.pdf',
        d.seed_tag = 'sprint23_smoke'

    MERGE (sec:Section {uid: 'sec-methods'})
    SET sec.title = 'Methods', sec.seed_tag = 'sprint23_smoke'
    MERGE (d)-[:HAS_SECTION]->(sec)

    MERGE (p:Passage {uid: 'passage-methods-1'})
    SET p.text = 'The Transformer model relies entirely on self-attention without recurrence.',
        p.page_number = 4,
        p.seed_tag = 'sprint23_smoke'
    MERGE (sec)-[:HAS_PASSAGE]->(p)

    MERGE (method:Method {uid: 'm-transformer'})
    SET method.display_name = 'Transformer',
        method.canonical_name = 'Transformer',
        method.seed_tag = 'sprint23_smoke'
    MERGE (concept:Concept {uid: 'c-self-attention'})
    SET concept.display_name = 'Self-Attention',
        concept.seed_tag = 'sprint23_smoke'
    MERGE (task:Task {uid: 't-machine-translation'})
    SET task.display_name = 'Machine Translation',
        task.seed_tag = 'sprint23_smoke'

    MERGE (ri1:RelationInstance {uid: 'ri-transformer-uses'})
    SET ri1.type = 'USES',
        ri1.confidence = 0.91,
        ri1.seed_tag = 'sprint23_smoke'
    MERGE (ri2:RelationInstance {uid: 'ri-transformer-task'})
    SET ri2.type = 'APPLIED_TO',
        ri2.confidence = 0.83,
        ri2.seed_tag = 'sprint23_smoke'
    MERGE (ri3:RelationInstance {uid: 'ri-self-attention-supports'})
    SET ri3.type = 'SUPPORTS',
        ri3.confidence = 0.85,
        ri3.seed_tag = 'sprint23_smoke'

    MERGE (method)-[:OUT_REL]->(ri1)
    MERGE (ri1)-[:TO]->(concept)
    MERGE (method)-[:OUT_REL]->(ri2)
    MERGE (ri2)-[:TO]->(task)
    MERGE (concept)-[:OUT_REL]->(ri3)
    MERGE (ri3)-[:TO]->(method)

    MERGE (ev1:Evidence {uid: 'ev-transformer-1'})
    SET ev1.text = 'The Transformer model relies entirely on attention mechanisms.',
        ev1.confidence = 0.9,
        ev1.seed_tag = 'sprint23_smoke'
    MERGE (ev2:Evidence {uid: 'ev-transformer-2'})
    SET ev2.text = 'Self-attention enables long-range dependency modeling.',
        ev2.confidence = 0.84,
        ev2.seed_tag = 'sprint23_smoke'
    MERGE (ev1)-[:SUPPORTS]->(ri1)
    MERGE (ev2)-[:SUPPORTS]->(ri3)
    MERGE (ev1)-[:FROM_PASSAGE]->(p)
    MERGE (ev2)-[:FROM_PASSAGE]->(p)

    MERGE (ic:InlineCitation {uid: 'ic-12'})
    SET ic.raw_text = '[12]',
        ic.reference_labels = ['[12]'],
        ic.seed_tag = 'sprint23_smoke'
    MERGE (ref:ReferenceEntry {uid: 'ref-vaswani-2017'})
    SET ref.title_guess = 'Attention Is All You Need',
        ref.year = 2017,
        ref.citation_key_numeric = '[12]',
        ref.seed_tag = 'sprint23_smoke'
    MERGE (p)-[:HAS_INLINE_CITATION]->(ic)
    MERGE (ic)-[:REFERS_TO]->(ref)

    MERGE (canonical:CanonicalEntity {uid: 'can-transformer'})
    SET canonical.entity_type = 'Method',
        canonical.canonical_name = 'Transformer',
        canonical.aliases = ['transformer architecture', 'attention model'],
        canonical.normalized_aliases = ['transformer architecture', 'attention model'],
        canonical.acronyms = ['tr'],
        canonical.link_reason = 'seeded_for_smoke',
        canonical.link_confidence = 0.95,
        canonical.seed_tag = 'sprint23_smoke'
    MERGE (method)-[icl:INSTANCE_OF_CANONICAL]->(canonical)
    SET icl.reason = 'seeded_for_smoke', icl.confidence = 0.95
    """
    db.execute_query_with_retry(create_query, {"document_id": SEED_DOCUMENT_ID})
    print(f"Seed complete. SMOKE_DOCUMENT_ID={SEED_DOCUMENT_ID}")


if __name__ == "__main__":
    run_seed()
