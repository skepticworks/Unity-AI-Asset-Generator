"""Atomic JSON persistence for local generation batches."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import BatchNotFoundError, BatchRequestInvalidError, FieldIssue
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.batches import BatchRecord

logger = get_logger(__name__)


def validate_batch_id(batch_id: str) -> str:
    """Accept only UUID batch identifiers (rejects path traversal)."""
    raw = batch_id.strip()
    if not raw:
        raise BatchRequestInvalidError(
            "batch_id must not be empty",
            field_issues={
                "batch_id": [
                    FieldIssue(code=FieldIssueCode.FIELD_REQUIRED, message="batch_id is required.")
                ]
            },
        )
    if "/" in raw or "\\" in raw or ".." in raw:
        raise BatchRequestInvalidError(
            "batch_id must not contain path segments",
            field_issues={
                "batch_id": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_INVALID,
                        message="batch_id must not contain path segments.",
                        actual=raw,
                    )
                ]
            },
        )
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise BatchRequestInvalidError(
            "batch_id must be a valid UUID",
            field_issues={
                "batch_id": [
                    FieldIssue(
                        code=FieldIssueCode.FORMAT_INVALID,
                        message="batch_id must be a valid UUID.",
                        actual=raw,
                    )
                ]
            },
        ) from exc


class BatchStore:
    """Thread-safe on-disk batch records."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._records: dict[str, BatchRecord] = {}
        self.reload()

    @property
    def directory(self) -> Path:
        return self._directory

    def _path_for(self, batch_id: str) -> Path:
        return self._directory / f"{batch_id}.json"

    def reload(self) -> None:
        with self._lock:
            self._records.clear()
            for path in sorted(self._directory.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(payload, dict):
                        continue
                    record = BatchRecord.from_dict(payload)
                except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
                    logger.warning("Skipping unreadable batch file %s", path.name)
                    continue
                self._records[record.batch_id] = record

    def _atomic_write(self, record: BatchRecord) -> None:
        path = self._path_for(record.batch_id)
        payload = json.dumps(record.to_dict(), indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{record.batch_id}.",
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

    def save(self, record: BatchRecord) -> BatchRecord:
        with self._lock:
            self._atomic_write(record)
            self._records[record.batch_id] = record
            return record

    def get(self, batch_id: str) -> BatchRecord:
        batch_id = validate_batch_id(batch_id)
        with self._lock:
            record = self._records.get(batch_id)
            if record is None:
                path = self._path_for(batch_id)
                if not path.is_file():
                    raise BatchNotFoundError(f"Batch '{batch_id}' was not found.")
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = BatchRecord.from_dict(payload)
                self._records[batch_id] = record
            return record

    def list_records(self, *, limit: int = 50, offset: int = 0) -> tuple[list[BatchRecord], int]:
        with self._lock:
            records = list(self._records.values())
        records.sort(key=lambda item: item.created_at, reverse=True)
        total = len(records)
        return records[offset : offset + limit], total

    def all_records(self) -> list[BatchRecord]:
        with self._lock:
            return list(self._records.values())

    def snapshot(self, batch_id: str) -> dict[str, Any]:
        return self.get(batch_id).to_dict()
