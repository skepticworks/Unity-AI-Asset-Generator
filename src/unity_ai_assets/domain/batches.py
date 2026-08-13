"""Domain models for batch orchestration over persistent generation jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from unity_ai_assets.core.version import BATCH_RECORD_SCHEMA_VERSION
from unity_ai_assets.domain.enums import BatchState, JobState
from unity_ai_assets.domain.jobs import JobRecord, utc_now_iso


@dataclass(frozen=True, slots=True)
class BatchJobCounts:
    """Job-state tallies used for batch summaries and progress."""

    queued: int = 0
    running: int = 0
    cancelling: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    interrupted: int = 0

    @property
    def total(self) -> int:
        return (
            self.queued
            + self.running
            + self.cancelling
            + self.completed
            + self.failed
            + self.cancelled
            + self.interrupted
        )

    @property
    def active(self) -> int:
        return self.queued + self.running + self.cancelling

    @property
    def terminal(self) -> int:
        return self.completed + self.failed + self.cancelled + self.interrupted

    def to_dict(self) -> dict[str, int]:
        return {
            "queued": self.queued,
            "running": self.running,
            "cancelling": self.cancelling,
            "completed": self.completed,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "interrupted": self.interrupted,
            "total": self.total,
            "active": self.active,
            "terminal": self.terminal,
        }


def count_job_states(jobs: list[JobRecord]) -> BatchJobCounts:
    """Tally member jobs by lifecycle state."""
    queued = running = cancelling = completed = failed = cancelled = interrupted = 0
    for job in jobs:
        if job.state is JobState.QUEUED:
            queued += 1
        elif job.state is JobState.RUNNING:
            running += 1
        elif job.state is JobState.CANCELLING:
            cancelling += 1
        elif job.state is JobState.COMPLETED:
            completed += 1
        elif job.state is JobState.FAILED:
            failed += 1
        elif job.state is JobState.CANCELLED:
            cancelled += 1
        elif job.state is JobState.INTERRUPTED:
            interrupted += 1
    return BatchJobCounts(
        queued=queued,
        running=running,
        cancelling=cancelling,
        completed=completed,
        failed=failed,
        cancelled=cancelled,
        interrupted=interrupted,
    )


def aggregate_batch_state(
    jobs: list[JobRecord],
    *,
    cancel_requested: bool = False,
) -> BatchState:
    """Derive a batch-level state from member jobs. One failure is not total failure."""
    if not jobs:
        return BatchState.FAILED
    counts = count_job_states(jobs)
    if counts.active > 0:
        if cancel_requested or counts.cancelling > 0:
            return BatchState.CANCELLING
        if counts.running > 0:
            return BatchState.RUNNING
        return BatchState.QUEUED
    if counts.completed == counts.total:
        return BatchState.COMPLETED
    if counts.completed > 0:
        return BatchState.PARTIAL_SUCCESS
    if counts.failed == 0 and (counts.cancelled > 0 or counts.interrupted > 0):
        return BatchState.CANCELLED
    return BatchState.FAILED


@dataclass
class BatchRecord:
    """Persistent batch grouping. Execution still belongs to individual jobs."""

    batch_id: str
    created_at: str
    updated_at: str
    seed_mode: str
    variation_count: int
    prompts: list[str]
    job_ids: list[str]
    seed: int | None = None
    seed_start: int | None = None
    seed_end: int | None = None
    resolved_base_seeds: list[int] = field(default_factory=list)
    cancel_requested: bool = False
    generation_profile_id: str | None = None
    asset_type: str = "texture"
    operation: str = "text_to_image"
    output_name: str = "texture"
    request_template: dict[str, Any] = field(default_factory=dict)
    schema_version: str = BATCH_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "seed_mode": self.seed_mode,
            "variation_count": self.variation_count,
            "prompts": list(self.prompts),
            "job_ids": list(self.job_ids),
            "seed": self.seed,
            "seed_start": self.seed_start,
            "seed_end": self.seed_end,
            "resolved_base_seeds": list(self.resolved_base_seeds),
            "cancel_requested": self.cancel_requested,
            "generation_profile_id": self.generation_profile_id,
            "asset_type": self.asset_type,
            "operation": self.operation,
            "output_name": self.output_name,
            "request_template": dict(self.request_template),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BatchRecord:
        prompts_raw = payload.get("prompts") or []
        job_ids_raw = payload.get("job_ids") or []
        seeds_raw = payload.get("resolved_base_seeds") or []
        template = payload.get("request_template") or {}
        return cls(
            batch_id=str(payload["batch_id"]),
            created_at=str(payload.get("created_at") or utc_now_iso()),
            updated_at=str(payload.get("updated_at") or utc_now_iso()),
            seed_mode=str(payload.get("seed_mode") or "random"),
            variation_count=int(payload.get("variation_count") or 1),
            prompts=[str(item) for item in prompts_raw],
            job_ids=[str(item) for item in job_ids_raw],
            seed=payload.get("seed"),
            seed_start=payload.get("seed_start"),
            seed_end=payload.get("seed_end"),
            resolved_base_seeds=[int(item) for item in seeds_raw],
            cancel_requested=bool(payload.get("cancel_requested", False)),
            generation_profile_id=payload.get("generation_profile_id"),
            asset_type=str(payload.get("asset_type") or "texture"),
            operation=str(payload.get("operation") or "text_to_image"),
            output_name=str(payload.get("output_name") or "texture"),
            request_template=dict(template) if isinstance(template, dict) else {},
            schema_version=str(payload.get("schema_version") or BATCH_RECORD_SCHEMA_VERSION),
        )
