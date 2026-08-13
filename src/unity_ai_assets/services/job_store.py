"""Atomic JSON persistence for local generation jobs."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections import deque
from pathlib import Path
from typing import Any
from uuid import UUID

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import FieldIssue, GenerationRequestInvalidError, JobNotFoundError
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.enums import JobState
from unity_ai_assets.domain.jobs import JobRecord

logger = get_logger(__name__)


def validate_job_id(job_id: str) -> str:
    """Accept only UUID job identifiers (rejects path traversal)."""
    raw = job_id.strip()
    if not raw:
        raise GenerationRequestInvalidError(
            "job_id must not be empty",
            field_issues={
                "job_id": [
                    FieldIssue(
                        code=FieldIssueCode.FIELD_REQUIRED,
                        message="job_id is required.",
                    )
                ]
            },
        )
    if "/" in raw or "\\" in raw or ".." in raw:
        raise GenerationRequestInvalidError(
            "job_id must not contain path segments",
            field_issues={
                "job_id": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_INVALID,
                        message="job_id must not contain path segments.",
                        actual=raw,
                    )
                ]
            },
        )
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise GenerationRequestInvalidError(
            "job_id must be a valid UUID",
            field_issues={
                "job_id": [
                    FieldIssue(
                        code=FieldIssueCode.FORMAT_INVALID,
                        message="job_id must be a valid UUID.",
                        actual=raw,
                    )
                ]
            },
        ) from exc


class JobStore:
    """Thread-safe on-disk job records plus an in-memory FIFO of queued IDs."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._records: dict[str, JobRecord] = {}
        self._queue: deque[str] = deque()
        self.reload()

    @property
    def directory(self) -> Path:
        return self._directory

    def _path_for(self, job_id: str) -> Path:
        return self._directory / f"{job_id}.json"

    def reload(self) -> None:
        """Load every job file and rebuild the queued FIFO by created_at."""
        with self._lock:
            self._records.clear()
            self._queue.clear()
            queued: list[JobRecord] = []
            for path in sorted(self._directory.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(payload, dict):
                        continue
                    record = JobRecord.from_dict(payload)
                except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
                    logger.warning("Skipping unreadable job file %s", path.name)
                    continue
                self._records[record.job_id] = record
                if record.state is JobState.QUEUED:
                    queued.append(record)
            queued.sort(key=lambda item: (item.created_at, item.job_id))
            self._queue.extend(item.job_id for item in queued)

    def _atomic_write(self, record: JobRecord) -> None:
        path = self._path_for(record.job_id)
        payload = json.dumps(record.to_dict(), indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{record.job_id}.",
            suffix=".tmp",
            dir=self._directory,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def save(self, record: JobRecord) -> JobRecord:
        """Persist a record and keep the in-memory index in sync."""
        with self._lock:
            self._atomic_write(record)
            self._records[record.job_id] = record
            return record

    def get(self, job_id: str) -> JobRecord:
        job_id = validate_job_id(job_id)
        with self._lock:
            record = self._records.get(job_id)
            if record is None:
                path = self._path_for(job_id)
                if not path.is_file():
                    raise JobNotFoundError(f"Job '{job_id}' was not found.")
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = JobRecord.from_dict(payload)
                self._records[job_id] = record
            return record

    def enqueue(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._queue:
                self._queue.append(job_id)

    def remove_from_queue(self, job_id: str) -> bool:
        with self._lock:
            try:
                self._queue.remove(job_id)
                return True
            except ValueError:
                return False

    def claim_next(self) -> JobRecord | None:
        """Pop the next queued job ID that is still queued. Caller must persist the claim."""
        with self._lock:
            while self._queue:
                job_id = self._queue.popleft()
                record = self._records.get(job_id)
                if record is None or record.state is not JobState.QUEUED:
                    continue
                return record
            return None

    def queued_ids(self) -> list[str]:
        with self._lock:
            return list(self._queue)

    def list_records(
        self,
        *,
        state: JobState | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[JobRecord], int]:
        with self._lock:
            records = list(self._records.values())
        records.sort(key=lambda item: item.created_at, reverse=True)
        if state is not None:
            records = [item for item in records if item.state is state]
        total = len(records)
        sliced = records[offset : offset + limit]
        return sliced, total

    def all_records(self) -> list[JobRecord]:
        with self._lock:
            return list(self._records.values())

    def snapshot(self, job_id: str) -> dict[str, Any]:
        return self.get(job_id).to_dict()
