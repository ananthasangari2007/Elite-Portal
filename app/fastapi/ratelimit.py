"""Small in-process rate limiter for sensitive auth endpoints.

Keeps the limits the Flask API enforced via Flask-Limiter (login 10/min,
register 5/h, forgot/reset 5-10/h, avatar 20/h). State is per worker process,
which matches the previous ``memory://`` limiter storage. Disable with
``RATELIMIT_ENABLED=false`` (used by the test-suite).
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.fastapi.auth import ApiError

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_MAX_KEYS = 50_000


def _enabled() -> bool:
    return os.getenv("RATELIMIT_ENABLED", "true").lower() not in {"0", "false", "no"}


def rate_limit(bucket: str, limit: int, window_seconds: int):
    """FastAPI dependency factory: allow ``limit`` calls per ``window_seconds`` per client IP."""

    def dependency(request: Request):
        if not _enabled():
            return
        client = request.client.host if request.client else "unknown"
        key = (bucket, client)
        now = time.monotonic()
        with _lock:
            if len(_hits) > _MAX_KEYS:
                _hits.clear()
            hits = _hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = int(window_seconds - (now - hits[0])) + 1
                raise ApiError(
                    "Too many attempts. Please wait a moment and try again.",
                    429,
                    "rate_limited",
                    {"retry_after_seconds": retry_after},
                )
            hits.append(now)

    return dependency
