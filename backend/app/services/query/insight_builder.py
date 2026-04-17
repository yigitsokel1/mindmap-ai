"""Build evidence-backed insight statements from clusters."""

from __future__ import annotations

from collections import defaultdict
from typing import List, Sequence

from backend.app.schemas.semantic_query import EvidenceClusterItem, InsightItem

MAX_INSIGHTS = 5
MIN_SUPPORTING_CLUSTERS = 2
MIN_CLUSTER_IMPORTANCE = 0.45
MIN_CLUSTER_CITATIONS = 1
MIN_EVIDENCE_DIVERSITY = 2
LOW_CONFIDENCE_THRESHOLD = 0.55


class InsightBuilder:
    """Extracts deterministic, evidence-backed insights."""

    def build(self, clusters: Sequence[EvidenceClusterItem]) -> List[InsightItem]:
        if not clusters:
            return []
        eligible_clusters = [cluster for cluster in clusters if self._cluster_is_reliable(cluster)]
        if not eligible_clusters:
            return []

        insights: List[InsightItem] = []
        insights.extend(self._common_patterns(eligible_clusters))
        insights.extend(self._frequent_relations(eligible_clusters))
        insights.extend(self._cross_document_trends(eligible_clusters))
        return self._filter_and_rank(insights)

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
            if cluster.canonical_frequency < 2:
                # Guardrail: avoid trend claims from single weak mentions.
                continue
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

    def _cluster_is_reliable(self, cluster: EvidenceClusterItem) -> bool:
        evidence_documents = {
            evidence.document_name or evidence.document_id
            for evidence in cluster.evidences
            if evidence.document_name or evidence.document_id
        }
        has_diversity = len(evidence_documents) >= MIN_EVIDENCE_DIVERSITY or len(cluster.evidences) >= MIN_EVIDENCE_DIVERSITY
        if not has_diversity:
            return False
        if cluster.importance < MIN_CLUSTER_IMPORTANCE:
            return False
        if cluster.citation_count < MIN_CLUSTER_CITATIONS and cluster.canonical_frequency < MIN_SUPPORTING_CLUSTERS:
            return False
        return True

    def _filter_and_rank(self, insights: Sequence[InsightItem]) -> List[InsightItem]:
        deduped: List[InsightItem] = []
        seen_texts: set[str] = set()
        for insight in sorted(insights, key=lambda item: item.confidence, reverse=True):
            text_key = insight.text.strip().lower()
            if not text_key or text_key in seen_texts:
                continue
            if insight.confidence < LOW_CONFIDENCE_THRESHOLD:
                continue
            if len(insight.supporting_clusters) < 1:
                continue
            seen_texts.add(text_key)
            deduped.append(insight)
            if len(deduped) >= MAX_INSIGHTS:
                break
        return deduped
