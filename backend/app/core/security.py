"""Lightweight API hardening utilities (auth, limits, throttling)."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import Header, HTTPException, Request


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SecurityConfig:
    semantic_api_key: str | None = os.getenv("SEMANTIC_API_KEY")
    require_api_key: bool = _as_bool(os.getenv("REQUIRE_API_KEY"), default=False)
    ingest_rate_limit_per_minute: int = int(os.getenv("INGEST_RATE_LIMIT_PER_MINUTE", "12"))
    query_rate_limit_per_minute: int = int(os.getenv("QUERY_RATE_LIMIT_PER_MINUTE", "60"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    max_upload_pages: int = int(os.getenv("MAX_UPLOAD_PAGES", "120"))
    allow_legacy_ingest: bool = _as_bool(os.getenv("ALLOW_LEGACY_INGEST"), default=False)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


security_config = SecurityConfig()


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded. Please retry shortly.")
            bucket.append(now)


rate_limiter = InMemoryRateLimiter()


def _client_key(request: Request, route_name: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{route_name}:{host}"


def enforce_ingest_rate_limit(request: Request) -> None:
    rate_limiter.check(
        key=_client_key(request, "ingest"),
        limit=security_config.ingest_rate_limit_per_minute,
    )


def enforce_query_rate_limit(request: Request) -> None:
    rate_limiter.check(
        key=_client_key(request, "query"),
        limit=security_config.query_rate_limit_per_minute,
    )


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = security_config.semantic_api_key
    if not security_config.require_api_key:
        return
    if not expected:
        raise HTTPException(status_code=500, detail="API key enforcement enabled but SEMANTIC_API_KEY is missing.")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")
