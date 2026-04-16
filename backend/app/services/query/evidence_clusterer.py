"""Cluster and deduplicate ranked evidence for insight extraction."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Sequence

from backend.app.schemas.semantic_query import CandidateEntity, EvidenceClusterItem, SemanticEvidenceItem


class EvidenceClusterer:
    """Groups evidence by canonical entity, relation and normalized snippet."""

    def build_clusters(
        self,
        evidence: Sequence[SemanticEvidenceItem],
        candidates: Sequence[CandidateEntity],
    ) -> List[EvidenceClusterItem]:
        if not evidence:
            return []
        entity_by_id = {item.entity_id: item.name for item in candidates}
        grouped: Dict[str, List[SemanticEvidenceItem]] = defaultdict(list)
        seen_by_cluster: Dict[str, set[str]] = defaultdict(set)
        for item in evidence:
            entity_name = self._resolve_entity_name(item, entity_by_id)
            relation = (item.relation_type or "RELATED_TO").upper()
            normalized_snippet = self._normalize_text(item.snippet)
            cluster_key = f"{self._normalize_text(entity_name)}::{relation}::{normalized_snippet[:72]}"
            if normalized_snippet in seen_by_cluster[cluster_key]:
                continue
            seen_by_cluster[cluster_key].add(normalized_snippet)
            enriched = item.model_copy(update={"cluster_key": cluster_key})
            grouped[cluster_key].append(enriched)

        clusters: List[EvidenceClusterItem] = []
        for cluster_key, items in grouped.items():
            first = items[0]
            entity_name = self._resolve_entity_name(first, entity_by_id)
            citation_count = sum(1 for ev in items if ev.citation_label or ev.reference_entry_id)
            importance_raw = min(1.0, (0.2 * len(items)) + (0.1 * citation_count))
            clusters.append(
                EvidenceClusterItem(
                    cluster_key=cluster_key,
                    entity=entity_name,
                    relation_type=(first.relation_type or "RELATED_TO").upper(),
                    evidences=items,
                    canonical_frequency=len(items),
                    citation_count=citation_count,
                    importance=round(importance_raw, 2),
                )
            )
        return sorted(clusters, key=lambda c: (c.importance, c.canonical_frequency), reverse=True)

    @staticmethod
    def _resolve_entity_name(item: SemanticEvidenceItem, entity_by_id: Dict[str, str]) -> str:
        if item.related_node_ids:
            for node_id in item.related_node_ids:
                if node_id in entity_by_id:
                    return entity_by_id[node_id]
        return "unknown_entity"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())
