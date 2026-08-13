"""Batch orchestration over the existing persistent job queue."""

from __future__ import annotations

import uuid
from typing import Any

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import (
    JobNotCancellableError,
    JobNotRetryableError,
    JobStateConflictError,
)
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.batches import (
    BatchJobCounts,
    BatchRecord,
    aggregate_batch_state,
    count_job_states,
)
from unity_ai_assets.domain.enums import BatchState
from unity_ai_assets.domain.jobs import JobRecord, prompt_summary, utc_now_iso
from unity_ai_assets.services.batch_expansion import BatchExpansionPlan, expand_batch
from unity_ai_assets.services.batch_store import BatchStore, validate_batch_id
from unity_ai_assets.services.job_service import JobService
from unity_ai_assets.services.job_store import JobStore

logger = get_logger(__name__)


def _redact_template(payload: dict[str, Any]) -> dict[str, Any]:
    """Store shared generation parameters without bulky image bytes."""
    redacted = dict(payload)
    for key in ("source_image", "mask_image"):
        value = redacted.get(key)
        if isinstance(value, dict):
            slim = {k: v for k, v in value.items() if k != "content_base64" and v is not None}
            slim["present"] = bool(value.get("content_base64"))
            redacted[key] = slim
    redacted.pop("prompt", None)
    redacted.pop("seed", None)
    redacted.pop("output_name", None)
    return redacted


class BatchService:
    """Expands a batch into normal jobs and aggregates their persisted states."""

    def __init__(
        self,
        store: BatchStore,
        job_service: JobService,
        settings: Settings,
    ) -> None:
        self._store = store
        self._job_service = job_service
        self._settings = settings

    @property
    def store(self) -> BatchStore:
        return self._store

    def preview(
        self,
        *,
        prompts: list[str],
        seed_mode: str,
        variation_count: int,
        seed: int | None = None,
        seed_start: int | None = None,
        seed_end: int | None = None,
        output_name: str = "texture",
    ) -> BatchExpansionPlan:
        """Validate and expand without creating jobs."""
        return self._expand(
            prompts=prompts,
            seed_mode=seed_mode,
            variation_count=variation_count,
            seed=seed,
            seed_start=seed_start,
            seed_end=seed_end,
            output_name=output_name,
        )

    def submit(
        self,
        *,
        prompts: list[str],
        seed_mode: str,
        variation_count: int,
        request: dict[str, Any],
        seed: int | None = None,
        seed_start: int | None = None,
        seed_end: int | None = None,
    ) -> tuple[BatchRecord, list[JobRecord], BatchExpansionPlan]:
        """Expand, persist the batch, and enqueue one job per expanded item."""
        output_name = str(request.get("output_name") or "texture")
        plan = self._expand(
            prompts=prompts,
            seed_mode=seed_mode,
            variation_count=variation_count,
            seed=seed,
            seed_start=seed_start,
            seed_end=seed_end,
            output_name=output_name,
        )
        now = utc_now_iso()
        prompt_by_index = {
            item.prompt_index: item.prompt
            for item in plan.items
        }
        ordered_prompts = [prompt_by_index[index] for index in sorted(prompt_by_index)]
        batch = BatchRecord(
            batch_id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            seed_mode=plan.seed_mode,
            variation_count=plan.variation_count,
            prompts=ordered_prompts,
            job_ids=[],
            seed=plan.base_seeds[0] if plan.seed_mode != "sequential" else seed,
            seed_start=seed_start if plan.seed_mode == "sequential" else None,
            seed_end=seed_end if plan.seed_mode == "sequential" else None,
            resolved_base_seeds=list(plan.base_seeds),
            generation_profile_id=request.get("generation_profile_id"),
            asset_type=str(request.get("asset_type") or "texture"),
            operation=str(request.get("operation") or "text_to_image"),
            output_name=output_name,
            request_template=_redact_template(request),
        )
        self._store.save(batch)

        jobs: list[JobRecord] = []
        try:
            for item in plan.items:
                payload = dict(request)
                payload["prompt"] = item.prompt
                payload["seed"] = item.seed
                payload["output_name"] = item.output_name
                record = self._job_service.submit(
                    payload,
                    batch_id=batch.batch_id,
                    batch_index=item.index,
                    prompt_index=item.prompt_index,
                    variation_index=item.variation_index,
                )
                jobs.append(record)
                batch.job_ids.append(record.job_id)
                batch.updated_at = utc_now_iso()
                self._store.save(batch)
        except Exception:
            batch.updated_at = utc_now_iso()
            self._store.save(batch)
            raise

        logger.info(
            "Submitted batch_id=%s jobs=%s seed_mode=%s",
            batch.batch_id,
            len(jobs),
            plan.seed_mode,
        )
        return batch, jobs, plan

    def get(
        self, batch_id: str
    ) -> tuple[BatchRecord, list[JobRecord], BatchState, BatchJobCounts]:
        record = self._store.get(validate_batch_id(batch_id))
        jobs = self._jobs_for(record)
        counts = count_job_states(jobs)
        state = aggregate_batch_state(jobs, cancel_requested=record.cancel_requested)
        return record, jobs, state, counts

    def list_batches(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[tuple[BatchRecord, list[JobRecord], BatchState, BatchJobCounts]], int]:
        records, total = self._store.list_records(limit=limit, offset=offset)
        items: list[tuple[BatchRecord, list[JobRecord], BatchState, BatchJobCounts]] = []
        for record in records:
            jobs = self._jobs_for(record)
            counts = count_job_states(jobs)
            state = aggregate_batch_state(jobs, cancel_requested=record.cancel_requested)
            items.append((record, jobs, state, counts))
        return items, total

    def cancel(
        self, batch_id: str
    ) -> tuple[BatchRecord, list[JobRecord], BatchState, BatchJobCounts]:
        """Cancel queued/running members. Completed jobs are left untouched."""
        record = self._store.get(validate_batch_id(batch_id))
        record.cancel_requested = True
        record.updated_at = utc_now_iso()
        self._store.save(record)
        for job_id in record.job_ids:
            try:
                job = self._job_service.get(job_id)
            except Exception:
                continue
            if not job.is_cancellable:
                continue
            try:
                self._job_service.cancel(job_id)
            except (JobNotCancellableError, JobStateConflictError):
                continue
        return self.get(record.batch_id)

    def retry_failed(
        self, batch_id: str
    ) -> tuple[BatchRecord, list[JobRecord], BatchState, BatchJobCounts]:
        """Retry eligible failed/interrupted/cancelled members. Successes stay completed."""
        record = self._store.get(validate_batch_id(batch_id))
        retried = 0
        for job_id in record.job_ids:
            try:
                job = self._job_service.get(job_id)
            except Exception:
                continue
            if not job.is_retryable:
                continue
            try:
                self._job_service.retry(job_id)
                retried += 1
            except (JobNotRetryableError, JobStateConflictError):
                continue
        record.cancel_requested = False
        record.updated_at = utc_now_iso()
        self._store.save(record)
        logger.info("Retry-failed batch_id=%s retried=%s", record.batch_id, retried)
        return self.get(record.batch_id)

    def _expand(
        self,
        *,
        prompts: list[str],
        seed_mode: str,
        variation_count: int,
        seed: int | None,
        seed_start: int | None,
        seed_end: int | None,
        output_name: str,
    ) -> BatchExpansionPlan:
        return expand_batch(
            prompts,
            seed_mode=seed_mode,
            variation_count=variation_count,
            seed=seed,
            seed_start=seed_start,
            seed_end=seed_end,
            output_name=output_name,
            min_seed=int(self._settings.min_seed),
            max_seed=int(self._settings.max_seed),
            max_jobs=int(self._settings.max_batch_jobs),
            max_prompts=int(self._settings.max_batch_prompts),
            max_variations=int(self._settings.max_batch_variations),
            max_prompt_length=int(self._settings.max_prompt_length),
            max_output_name_length=int(self._settings.max_output_name_length),
        )

    def _jobs_for(self, record: BatchRecord) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        job_store: JobStore = self._job_service.store
        for job_id in record.job_ids:
            try:
                jobs.append(job_store.get(job_id))
            except Exception:
                logger.warning(
                    "Batch %s references missing job %s", record.batch_id, job_id
                )
        jobs.sort(
            key=lambda item: (
                item.batch_index if item.batch_index is not None else 10_000,
                item.created_at,
                item.job_id,
            )
        )
        return jobs


def batch_prompt_summary(prompts: list[str], *, limit: int = 80) -> str:
    """Compact batch prompt preview for listings."""
    if not prompts:
        return ""
    if len(prompts) == 1:
        return prompt_summary(prompts[0], limit=limit)
    first = prompt_summary(prompts[0], limit=max(20, limit - 16))
    return f"{first} (+{len(prompts) - 1} more)"
