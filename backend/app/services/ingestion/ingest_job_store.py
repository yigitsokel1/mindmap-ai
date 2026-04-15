"""In-memory ingest job tracking for stage-based progress visibility."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

INGEST_STAGES = (
    "uploaded",
    "parsing",
    "detecting_sections",
    "parsing_references",
    "extracting_semantics",
    "writing_graph",
    "completed",
    "failed",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class IngestJob:
    job_id: str
    file_name: str
    mode: str
    stage: str = "uploaded"
    status: str = "running"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    document_id: str | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingest_job_id": self.job_id,
            "file_name": self.file_name,
            "mode": self.mode,
            "stage": self.stage,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "document_id": self.document_id,
            "error": self.error,
            "details": self.details,
        }


class IngestJobStore:
    """Thread-safe in-memory store for ingestion jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, IngestJob] = {}
        self._lock = threading.Lock()

    def create_job(self, file_name: str, mode: str) -> IngestJob:
        with self._lock:
            job_id = uuid.uuid4().hex
            job = IngestJob(job_id=job_id, file_name=file_name, mode=mode)
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> IngestJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_stage(self, job_id: str, stage: str, details: dict[str, Any] | None = None) -> IngestJob | None:
        if stage not in INGEST_STAGES:
            raise ValueError(f"Unknown ingest stage: {stage}")
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.stage = stage
            job.updated_at = _utc_now()
            if details:
                job.details.update(details)
            if stage == "completed":
                job.status = "completed"
            elif stage == "failed":
                job.status = "failed"
            else:
                job.status = "running"
            return job

    def mark_completed(self, job_id: str, document_id: str | None = None, details: dict[str, Any] | None = None) -> IngestJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if document_id:
                job.document_id = document_id
            if details:
                job.details.update(details)
            job.stage = "completed"
            job.status = "completed"
            job.updated_at = _utc_now()
            return job

    def mark_failed(self, job_id: str, error: str, details: dict[str, Any] | None = None) -> IngestJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.stage = "failed"
            job.status = "failed"
            job.error = error
            job.updated_at = _utc_now()
            if details:
                job.details.update(details)
            return job


ingest_job_store = IngestJobStore()
