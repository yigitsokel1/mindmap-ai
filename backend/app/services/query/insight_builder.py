"""Build evidence-backed insight statements from clusters."""

from __future__ import annotations

from collections import defaultdict
from typing import List, Sequence

from backend.app.schemas.semantic_query import EvidenceClusterItem, InsightItem


class InsightBuilder:
    """Extracts deterministic, evidence-backed insights."""

    def build(self, clusters: Sequence[EvidenceClusterItem]) -> List[InsightItem]:
        if not clusters:
            return []
        insights: List[InsightItem] = []
        insights.extend(self._common_patterns(clusters))
        insights.extend(self._frequent_relations(clusters))
        insights.extend(self._cross_document_trends(clusters))
        return insights[:5]

    def _common_patterns(self, clusters: Sequence[EvidenceClusterItem]) -> List[InsightItem]:
        items: List[InsightItem] = []
        for cluster in clusters:
            if cluster.canonical_frequency < 2:
                continue
            confidence = min(0.95, 0.5 + (0.1 * cluster.canonical_frequency))
            items.append(
                InsightItem(
                    type="COMMON_PATTERN",
                    text=f"{cluster.entity} most commonly appears with {cluster.relation_type} patterns.",
                    confidence=round(confidence, 2),
                    supporting_clusters=[cluster.cluster_key],
                )
            )
        return items

    def _frequent_relations(self, clusters: Sequence[EvidenceClusterItem]) -> List[InsightItem]:
        grouped = defaultdict(list)
        for cluster in clusters:
            grouped[cluster.relation_type].append(cluster)

        items: List[InsightItem] = []
        for relation_type, rel_clusters in grouped.items():
            if len(rel_clusters) < 2:
                continue
            support_keys = [item.cluster_key for item in rel_clusters]
            confidence = min(0.9, 0.45 + (0.08 * len(rel_clusters)))
            items.append(
                InsightItem(
                    type="FREQUENT_RELATION",
                    text=f"{relation_type} relation is frequently observed across matched entities.",
                    confidence=round(confidence, 2),
                    supporting_clusters=support_keys,
                )
            )
        return items

    def _cross_document_trends(self, clusters: Sequence[EvidenceClusterItem]) -> List[InsightItem]:
        items: List[InsightItem] = []
        for cluster in clusters:
            documents = {
                evidence.document_name or evidence.document_id
                for evidence in cluster.evidences
                if evidence.document_name or evidence.document_id
            }
            if len(documents) < 2:
                continue
            confidence = min(0.95, 0.55 + (0.1 * len(documents)))
            items.append(
                InsightItem(
                    type="CROSS_DOCUMENT_TREND",
                    text=f"{cluster.entity} {cluster.relation_type.lower()} trend repeats in {len(documents)} documents.",
                    confidence=round(confidence, 2),
                    supporting_clusters=[cluster.cluster_key],
                )
            )
        return items
