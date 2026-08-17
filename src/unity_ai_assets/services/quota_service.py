"""Single-process admission controls for a local job queue.

This implementation deliberately has process-local scope. Multi-replica deployments
must replace it with a shared quota provider rather than assuming synchronization.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import QuotaExceededError
from unity_ai_assets.domain.enums import JobState


class QuotaService:
    """Apply optional rate and queued-job limits before queue admission."""

    def __init__(self, settings: Settings) -> None:
        self._requests_per_minute = settings.max_requests_per_minute
        self._max_queued_jobs = settings.max_queued_jobs
        self._timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_request(self, client_id: str) -> None:
        """Enforce a sliding one-minute request window when configured."""
        if self._requests_per_minute == 0:
            return
        now = time.monotonic()
        with self._lock:
            timestamps = self._timestamps[client_id]
            while timestamps and timestamps[0] <= now - 60:
                timestamps.popleft()
            if len(timestamps) >= self._requests_per_minute:
                raise QuotaExceededError(
                    "Request rate limit exceeded. Retry after one minute.",
                    details={"limit": self._requests_per_minute, "window_seconds": 60},
                )
            timestamps.append(now)

    def check_queue(self, job_service: object, *, required_slots: int = 1) -> None:
        """Enforce queue depth using the existing job store, never a second queue."""
        if self._max_queued_jobs == 0:
            return
        records = job_service.store.all_records()  # type: ignore[attr-defined]
        queued = sum(record.state is JobState.QUEUED for record in records)
        if queued + required_slots > self._max_queued_jobs:
            raise QuotaExceededError(
                "The generation queue is full. Retry after queued jobs finish.",
                details={
                    "limit": self._max_queued_jobs,
                    "queued_jobs": queued,
                    "requested_slots": required_slots,
                },
            )
