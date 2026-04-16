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

from backend.app.schemas.semantic_query import SemanticEvidenceItem, SemanticQueryRequest
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


class FixtureNode:
    """Tiny node adapter that mimics graph entities from Neo4j records."""

    def __init__(self, node_id: str, node_type: str, display_name: str):
        self.element_id = node_id
        self.labels = [node_type]
        self._props = {"display_name": display_name}

    def get(self, key: str, default: Any = None) -> Any:
        return self._props.get(key, default)


class FixtureSemanticQueryService(SemanticQueryService):
    """Semantic service that reads deterministic graph data from fixtures."""

    def __init__(self, fixtures: Dict[str, Any]) -> None:
        self._fixtures = fixtures
        super().__init__()

    def _find_candidate_nodes(  # type: ignore[override]
        self,
        tokens: Sequence[str],
        document_id: str | None,
        node_types: Sequence[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not document_id:
            return []
        doc = self._fixtures.get(document_id)
        if not doc:
            return []

        token_set = {token.lower() for token in tokens}
        records: List[Dict[str, Any]] = []
        for entity in doc.get("entities", []):
            display = str(entity.get("display_name", ""))
            if node_types and entity.get("type") not in set(node_types):
                continue
            if not token_set or any(token in display.lower() for token in token_set):
                records.append(
                    {
                        "n": FixtureNode(
                            node_id=str(entity["id"]),
                            node_type=str(entity["type"]),
                            display_name=display,
                        )
                    }
                )
        if not records:
            for entity in doc.get("entities", [])[: min(2, limit)]:
                records.append(
                    {
                        "n": FixtureNode(
                            node_id=str(entity["id"]),
                            node_type=str(entity["type"]),
                            display_name=str(entity["display_name"]),
                        )
                    }
                )
        return records[:limit]

    def _collect_evidence(  # type: ignore[override]
        self,
        candidate_nodes: Sequence[Dict[str, Any]],
        max_evidence: int,
        document_id: str | None,
        traversal_plan: Any,
    ) -> List[SemanticEvidenceItem]:
        if not document_id:
            return []
        doc = self._fixtures.get(document_id)
        if not doc:
            return []

        candidate_ids = {
            str(record["n"].element_id) for record in candidate_nodes if isinstance(record.get("n"), FixtureNode)
        }
        items: List[SemanticEvidenceItem] = []
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
                    related_node_ids=[entity_id, f"ri-{document_id}-{idx}"],
                    document_id=document_id,
                    document_name=str(doc.get("name", "")),
                    citation_label=evidence.get("citation_label"),
                    reference_entry_id=evidence.get("reference_entry_id"),
                )
            )
            if len(items) >= max_evidence:
                break
        return items


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

        intent_correct += int(intent_ok)
        evidence_presence_correct += int(evidence_ok)
        citation_presence_correct += int(citation_ok)
        section_hits += int(section_ok)
        keyword_ratio_sum += keyword_ratio
        entity_recall_sum += recall

        print(f"[{case.case_id}]")
        print(f"  intent:   expected={case.expected_intent} actual={response.query_intent} ok={intent_ok}")
        print(f"  evidence: expected=True actual={bool(response.evidence)} ok={evidence_ok}")
        print(
            f"  citation: expected={case.expected_citation_presence} actual={bool(response.citations)} ok={citation_ok}"
        )
        print(f"  sections: expected={case.expected_sections} actual={sorted(actual_section_set)} ok={section_ok}")
        print(f"  keywords: ratio={keyword_ratio:.2f} expected={case.expected_keywords}")
        print(f"  entities: recall={recall:.2f} expected={case.expected_entities}")
        print("-" * 72)

    print("\nAggregate Metrics")
    print("=" * 72)
    print(f"Intent accuracy         : {intent_correct / total:.2%}")
    print(f"Evidence presence       : {evidence_presence_correct / total:.2%}")
    print(f"Citation presence       : {citation_presence_correct / total:.2%}")
    print(f"Section coverage        : {section_hits / total:.2%}")
    print(f"Keyword hit ratio       : {keyword_ratio_sum / total:.2%}")
    print(f"Matched entity recall   : {entity_recall_sum / total:.2%}")
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
