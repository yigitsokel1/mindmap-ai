"""Entity identity helpers.

Provides deterministic UID generation for graph entities.
The UID is the merge key in Neo4j — two entities with the
same UID are guaranteed to be the same node.
"""

import re
import unicodedata


def build_entity_uid(entity_type: str, canonical_name: str) -> str:
    """Build a deterministic UID from entity type and canonical name.

    Format: "{type_lower}:{slug}"
    Examples:
        ("Concept", "Self-Attention") → "concept:self-attention"
        ("Method", "Transformer") → "method:transformer"
        ("Dataset", "WMT 2014 English-German") → "dataset:wmt-2014-english-german"

    Args:
        entity_type: One of the valid entity type strings.
        canonical_name: The normalized entity name.

    Returns:
        A stable, lowercase UID string.
    """
    slug = _slugify(canonical_name)
    return f"{entity_type.lower()}:{slug}"


def build_relation_instance_uid(rel_type: str, source_uid: str, target_uid: str) -> str:
    """Build a deterministic RelationInstance UID.

    Format: "ri:{rel_slug}:{source_uid}:{target_uid}"
    Example:
        ("USES", "method:transformer", "concept:self-attention")
        -> "ri:uses:method:transformer:concept:self-attention"
    """
    rel_slug = _slugify(rel_type)
    return f"ri:{rel_slug}:{source_uid}:{target_uid}"


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug.

    Lowercases, removes accents, replaces non-alnum with hyphens,
    collapses consecutive hyphens, strips leading/trailing hyphens.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")
