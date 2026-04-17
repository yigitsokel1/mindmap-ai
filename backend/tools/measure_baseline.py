"""Lightweight latency baseline runner for launch readiness."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[Any, float]:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, method=method, data=body, headers=headers)
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return json.loads(raw.decode("utf-8")), round(elapsed_ms, 2)


def _multipart_upload(url: str, file_path: Path) -> float:
    boundary = "----mindmapai-baseline-boundary"
    content = file_path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode("utf-8"),
        b"Content-Type: application/pdf\r\n\r\n",
        content,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    payload = b"".join(parts)
    request = urllib.request.Request(
        url=url,
        method="POST",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=90):
        pass
    return round((time.perf_counter() - start) * 1000, 2)


def run_baseline(api_base: str, document_id: str, pdf_path: str | None, output: Path) -> None:
    api_base = api_base.rstrip("/")
    baseline: dict[str, Any] = {"api_base": api_base, "document_id": document_id, "measured_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    if pdf_path:
        baseline["ingest_latency_ms"] = _multipart_upload(f"{api_base}/api/ingest", Path(pdf_path))
    else:
        baseline["ingest_latency_ms"] = None
        baseline["ingest_note"] = "Skipped: pass --pdf-path to measure ingest latency."

    query_payload = {
        "question": "How is transformer grounded in this paper?",
        "document_id": document_id,
        "include_citations": True,
        "max_evidence": 5,
    }
    query_response, query_ms = _request_json(f"{api_base}/api/query/semantic", "POST", query_payload)
    baseline["query_latency_ms"] = query_ms

    graph_response, graph_ms = _request_json(
        f"{api_base}/api/graph/semantic?{urllib.parse.urlencode({'document_id': document_id, 'include_structural': 'true', 'include_evidence': 'true', 'include_citations': 'true'})}"
    )
    baseline["graph_fetch_latency_ms"] = graph_ms

    node_id = None
    for node in graph_response.get("nodes", []):
        if node.get("label") in {"Method", "Concept", "Task"}:
            node_id = node.get("id")
            break
    if node_id:
        _, node_ms = _request_json(f"{api_base}/api/graph/node/{node_id}?document_id={document_id}")
        baseline["node_detail_latency_ms"] = node_ms
    else:
        baseline["node_detail_latency_ms"] = None
        baseline["node_detail_note"] = "No suitable node found for node detail timing."

    two_hop_payload = {
        "question": "What trend exists across related entities for this method?",
        "document_id": document_id,
        "include_citations": True,
        "max_evidence": 8,
    }
    _, two_hop_ms = _request_json(f"{api_base}/api/query/semantic", "POST", two_hop_payload)
    baseline["two_hop_query_latency_ms"] = two_hop_ms
    baseline["query_response_meta"] = {
        "intent": query_response.get("query_intent"),
        "evidence_count": len(query_response.get("evidence", [])),
        "citation_count": len(query_response.get("citations", [])),
    }

    output.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(f"Baseline written to {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure launch baseline latencies.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--document-id", default="doc-transformer")
    parser.add_argument("--pdf-path", default=None)
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[2] / "docs" / "performance_baseline.latest.json"))
    args = parser.parse_args()
    try:
        run_baseline(args.api_base, args.document_id, args.pdf_path, Path(args.output))
    except urllib.error.URLError as exc:
        raise SystemExit(f"Baseline failed: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
