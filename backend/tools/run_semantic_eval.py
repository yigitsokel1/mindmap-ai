"""Deterministic semantic query evaluator for synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas.semantic_query import CandidateEntity, SemanticEvidenceItem, SemanticQueryRequest
from backend.app.services.query.candidate_selector import CandidateSelector
from backend.app.services.query.semantic_query_reader import SemanticQueryReader
from backend.app.services.query.semantic_query_service import SemanticQueryService


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    document_id: str
    question: str
    expected_intent: str
    expected_entities: List[str]
    expected_sections: List[str]
    expected_citation_presence: bool
    expected_keywords: List[str]
    expected_cross_document_hit: bool = False
    case_type: str = "baseline"
    expected_no_link: bool = False
    expects_alias_expansion: bool = False


class FixtureNode:
    """Tiny node adapter that mimics graph entities from Neo4j records."""

    def __init__(self, node_id: str, node_type: str, display_name: str):
        self.element_id = node_id
        self.labels = [node_type]
        self._props = {"display_name": display_name}

    def get(self, key: str, default: Any = None) -> Any:
        return self._props.get(key, default)


class FixtureSemanticQueryReader(SemanticQueryReader):
    """Fixture-backed reader for deterministic eval cases."""

    def __init__(self, fixtures: Dict[str, Any]) -> None:
        self._fixtures = fixtures

    def find_candidate_entities(
        self,
        tokens: Sequence[str],
        document_id: str | None,
        node_types: Sequence[str],
        limit: int = 20,
    ) -> List[CandidateEntity]:
        if not document_id:
            return []
        doc = self._fixtures.get(document_id)
        if not doc:
            return []

        token_set = {token.lower() for token in tokens}
        candidates: List[CandidateEntity] = []
        for entity in doc.get("entities", []):
            display = str(entity.get("display_name", ""))
            if node_types and entity.get("type") not in set(node_types):
                continue
            if not token_set or any(token in display.lower() for token in token_set):
                candidates.append(
                    CandidateEntity(
                        entity_id=str(entity["id"]),
                        type=str(entity["type"]),
                        name=display,
                        score=1.0,
                        match_reason="fixture_token_match",
                        source="local",
                    )
                )
        if not candidates:
            for entity in doc.get("entities", [])[: min(2, limit)]:
                candidates.append(
                    CandidateEntity(
                        entity_id=str(entity["id"]),
                        type=str(entity["type"]),
                        name=str(entity["display_name"]),
                        score=0.7,
                        match_reason="fixture_fallback",
                        source="local",
                    )
                )
        return candidates[:limit]

    def collect_evidence(
        self,
        candidates: Sequence[CandidateEntity],
        max_evidence: int,
        document_id: str | None,
        traversal_plan: Any,  # noqa: ARG002
    ) -> List[SemanticEvidenceItem]:
        candidate_ids = {candidate.entity_id for candidate in candidates}
        items: List[SemanticEvidenceItem] = []
        docs = []
        if document_id and document_id in self._fixtures:
            docs.append((document_id, self._fixtures[document_id]))
        for key, doc in self._fixtures.items():
            if key == document_id:
                continue
            docs.append((key, doc))

        for doc_id, doc in docs:
            for idx, evidence in enumerate(doc.get("evidence", [])):
                entity_id = str(evidence.get("entity_id"))
                if candidate_ids and entity_id not in candidate_ids:
                    continue
                items.append(
                    SemanticEvidenceItem(
                        relation_type=str(evidence.get("relation_type", "RELATED_TO")),
                        page=evidence.get("page"),
                        snippet=str(evidence.get("snippet", "")),
                        section=evidence.get("section"),
                        confidence=0.82,
                        related_node_ids=[entity_id, f"ri-{doc_id}-{idx}"],
                        document_id=doc_id,
                        document_name=str(doc.get("name", "")),
                        citation_label=evidence.get("citation_label"),
                        reference_entry_id=evidence.get("reference_entry_id"),
                    )
                )
                if len(items) >= max_evidence:
                    return items
        return items

    def lookup_canonical_candidates(self, tokens: Sequence[str]) -> List[CandidateEntity]:
        token_set = {token.lower() for token in tokens}
        if not token_set:
            return []
        candidates: List[CandidateEntity] = []
        for doc in self._fixtures.values():
            for entity in doc.get("entities", []):
                aliases = [str(alias).lower() for alias in entity.get("aliases", [])]
                canonical = str(entity.get("canonical_name", entity.get("display_name", ""))).lower()
                acronym = str(entity.get("acronym", "")).lower()
                if not token_set.intersection(set(aliases + [canonical, acronym])):
                    continue
                candidates.append(
                    CandidateEntity(
                        entity_id=str(entity["id"]),
                        type=str(entity["type"]),
                        name=str(entity["display_name"]),
                        score=0.9,
                        match_reason="fixture_canonical_match",
                        source="canonical-ready",
                    )
                )
        return candidates


class FixtureSemanticQueryService(SemanticQueryService):
    """Semantic service that reads deterministic graph data from fixtures."""

    def __init__(self, fixtures: Dict[str, Any]) -> None:
        super().__init__()
        self.reader = FixtureSemanticQueryReader(fixtures=fixtures)
        self.candidate_selector = CandidateSelector(self.reader)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_cases(raw: Dict[str, Any]) -> List[EvalCase]:
    return [
        EvalCase(
            case_id=str(item["id"]),
            document_id=str(item["document_id"]),
            question=str(item["question"]),
            expected_intent=str(item["expected_intent"]),
            expected_entities=[str(v) for v in item.get("expected_entities", [])],
            expected_sections=[str(v) for v in item.get("expected_sections", [])],
            expected_citation_presence=bool(item.get("expected_citation_presence", False)),
            expected_keywords=[str(v) for v in item.get("expected_keywords", [])],
            expected_cross_document_hit=bool(item.get("expected_cross_document_hit", False)),
            case_type=str(item.get("case_type", "baseline")),
            expected_no_link=bool(item.get("expected_no_link", False)),
            expects_alias_expansion=bool(item.get("expects_alias_expansion", False)),
        )
        for item in raw.get("cases", [])
    ]


def _keyword_hit_ratio(text: str, keywords: Sequence[str]) -> float:
    if not keywords:
        return 1.0
    haystack = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in haystack)
    return hits / len(keywords)


def _entity_recall(expected: Sequence[str], actual: Sequence[str]) -> float:
    if not expected:
        return 1.0
    actual_set = {item.lower() for item in actual}
    hits = sum(1 for ent in expected if ent.lower() in actual_set)
    return hits / len(expected)


def run_eval(fixtures_dir: Path) -> int:
    documents = _load_json(fixtures_dir / "documents.json")
    cases = _as_cases(_load_json(fixtures_dir / "cases.json"))
    fixture_map = {doc["id"]: doc for doc in documents.get("documents", [])}
    service = FixtureSemanticQueryService(fixtures=fixture_map)

    total = len(cases)
    if total == 0:
        print("No eval cases found.")
        return 1

    intent_correct = 0
    evidence_presence_correct = 0
    citation_presence_correct = 0
    section_hits = 0
    keyword_ratio_sum = 0.0
    entity_recall_sum = 0.0
    canonical_precision_sum = 0.0
    canonical_reuse_sum = 0.0
    cross_document_hits = 0
    no_link_total = 0
    no_link_correct = 0
    false_positive_total = 0
    false_positive_count = 0
    alias_cases_total = 0
    alias_success_count = 0

    print("\nSemantic Query Eval Report")
    print("=" * 72)
    for case in cases:
        response = service.answer(
            SemanticQueryRequest(
                question=case.question,
                document_id=case.document_id,
                include_citations=True,
                max_evidence=5,
            )
        )
        intent_ok = response.query_intent == case.expected_intent
        evidence_ok = bool(response.evidence)
        citation_ok = bool(response.citations) == case.expected_citation_presence
        expected_section_set = {s.lower() for s in case.expected_sections}
        actual_section_set = {str(item.section or "").lower() for item in response.evidence}
        section_ok = bool(expected_section_set.intersection(actual_section_set)) if expected_section_set else True
        combined_text = f"{response.answer} " + " ".join(item.snippet for item in response.evidence)
        keyword_ratio = _keyword_hit_ratio(combined_text, case.expected_keywords)
        recall = _entity_recall(
            case.expected_entities,
            [item.display_name for item in response.matched_entities],
        )
        canonical_matches = [item for item in response.matched_entities if item.display_name in case.expected_entities]
        canonical_precision = (len(canonical_matches) / len(response.matched_entities)) if response.matched_entities else 0.0
        matched_docs = {ev.document_id for ev in response.evidence if ev.document_id}
        cross_document_hit = len(matched_docs) > 1
        reuse_rate = len({item.display_name for item in response.matched_entities}) / len(response.matched_entities) if response.matched_entities else 0.0
        matched_entity_names = {item.display_name.lower() for item in response.matched_entities}
        expected_entity_names = {item.lower() for item in case.expected_entities}
        no_link_prediction = not response.matched_entities
        if case.expected_no_link:
            no_link_total += 1
            no_link_correct += int(no_link_prediction)
            false_positive_total += 1
            false_positive_count += int(not no_link_prediction)
        if case.expects_alias_expansion:
            alias_cases_total += 1
            alias_success_count += int(bool(expected_entity_names.intersection(matched_entity_names)))

        intent_correct += int(intent_ok)
        evidence_presence_correct += int(evidence_ok)
        citation_presence_correct += int(citation_ok)
        section_hits += int(section_ok)
        keyword_ratio_sum += keyword_ratio
        entity_recall_sum += recall
        canonical_precision_sum += canonical_precision
        canonical_reuse_sum += reuse_rate
        cross_document_hits += int(cross_document_hit == case.expected_cross_document_hit)

        print(f"[{case.case_id}]")
        print(f"  intent:   expected={case.expected_intent} actual={response.query_intent} ok={intent_ok}")
        print(f"  evidence: expected=True actual={bool(response.evidence)} ok={evidence_ok}")
        print(
            f"  citation: expected={case.expected_citation_presence} actual={bool(response.citations)} ok={citation_ok}"
        )
        print(f"  sections: expected={case.expected_sections} actual={sorted(actual_section_set)} ok={section_ok}")
        print(f"  keywords: ratio={keyword_ratio:.2f} expected={case.expected_keywords}")
        print(f"  entities: recall={recall:.2f} expected={case.expected_entities}")
        print(f"  canonical precision: {canonical_precision:.2f}")
        print(f"  canonical reuse rate: {reuse_rate:.2f}")
        print(
            f"  cross-document hit: expected={case.expected_cross_document_hit} actual={cross_document_hit} "
            f"ok={cross_document_hit == case.expected_cross_document_hit}"
        )
        print("-" * 72)

    print("\nAggregate Metrics")
    print("=" * 72)
    print(f"Intent accuracy         : {intent_correct / total:.2%}")
    print(f"Evidence presence       : {evidence_presence_correct / total:.2%}")
    print(f"Citation presence       : {citation_presence_correct / total:.2%}")
    print(f"Section coverage        : {section_hits / total:.2%}")
    print(f"Keyword hit ratio       : {keyword_ratio_sum / total:.2%}")
    print(f"Matched entity recall   : {entity_recall_sum / total:.2%}")
    print(f"Canonical link precision: {canonical_precision_sum / total:.2%}")
    print(f"Canonical entity reuse  : {canonical_reuse_sum / total:.2%}")
    print(f"Cross-doc hit presence  : {cross_document_hits / total:.2%}")
    if false_positive_total:
        print(f"False positive rate     : {false_positive_count / false_positive_total:.2%}")
        print(f"No-link correctness     : {no_link_correct / no_link_total:.2%}")
    if alias_cases_total:
        print(f"Alias expansion success : {alias_success_count / alias_cases_total:.2%}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic semantic query quality eval.")
    parser.add_argument(
        "--fixtures-dir",
        default=str(Path(__file__).resolve().parents[1] / "evals" / "semantic_query"),
        help="Path containing documents.json and cases.json",
    )
    args = parser.parse_args()
    return run_eval(Path(args.fixtures_dir))


if __name__ == "__main__":
    raise SystemExit(main())
