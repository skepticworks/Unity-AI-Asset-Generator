"""Public API schemas for batch generation orchestration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from unity_ai_assets.api.schemas.generation import TextureGenerationRequest
from unity_ai_assets.api.schemas.jobs import JobResponse
from unity_ai_assets.domain.batches import BatchJobCounts, BatchRecord
from unity_ai_assets.domain.enums import BatchState
from unity_ai_assets.domain.jobs import JobRecord
from unity_ai_assets.services.batch_expansion import BatchExpansionPlan
from unity_ai_assets.services.batch_service import batch_prompt_summary

BatchStateLiteral = Literal[
    "queued",
    "running",
    "cancelling",
    "completed",
    "partial_success",
    "failed",
    "cancelled",
]
SeedModeLiteral = Literal["fixed", "random", "sequential"]


class BatchJobCountsSchema(BaseModel):
    """Per-state job tallies for a batch."""

    queued: int = 0
    running: int = 0
    cancelling: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    interrupted: int = 0
    total: int = 0
    active: int = 0
    terminal: int = 0


class BatchProgressSchema(BaseModel):
    """Batch progress from real job counts. No invented inference percentages."""

    finished_jobs: int
    total_jobs: int
    completed_jobs: int


class BatchExpansionItemSchema(BaseModel):
    """One planned job in an expansion preview."""

    index: int
    prompt_index: int
    variation_index: int
    seed: int
    prompt: str
    prompt_summary: str
    output_name: str


class BatchPreviewResponse(BaseModel):
    """Dry-run expansion used before submission."""

    job_count: int
    prompt_count: int
    variation_count: int
    seed_mode: str
    base_seeds: list[int]
    seed_summary: str
    warnings: list[str] = Field(default_factory=list)
    items: list[BatchExpansionItemSchema]


class BatchSubmitRequest(BaseModel):
    """Submit a batch. Member jobs use the existing generation request model."""

    prompts: list[str] = Field(..., min_length=1)
    variation_count: int = Field(default=1, ge=1)
    seed_mode: SeedModeLiteral = "random"
    seed: int | None = None
    seed_start: int | None = None
    seed_end: int | None = None
    request: TextureGenerationRequest


class BatchResponse(BaseModel):
    """Public batch record with aggregated job state."""

    batch_id: str
    state: BatchStateLiteral
    created_at: str
    updated_at: str
    seed_mode: str
    variation_count: int
    prompts: list[str]
    prompt_summary: str
    job_ids: list[str]
    seed: int | None = None
    seed_start: int | None = None
    seed_end: int | None = None
    resolved_base_seeds: list[int] = Field(default_factory=list)
    seed_summary: str = ""
    cancel_requested: bool = False
    generation_profile_id: str | None = None
    asset_type: str
    operation: str
    output_name: str
    counts: BatchJobCountsSchema
    progress: BatchProgressSchema
    request: dict[str, Any] = Field(default_factory=dict)
    jobs: list[JobResponse] = Field(default_factory=list)

    @classmethod
    def from_record(
        cls,
        record: BatchRecord,
        jobs: list[JobRecord],
        state: BatchState,
        counts: BatchJobCounts,
        *,
        include_jobs: bool = True,
    ) -> BatchResponse:
        seed_values = [
            int(job.seed)
            for job in jobs
            if job.seed is not None and (job.prompt_index or 0) == 0
        ]
        if len(seed_values) <= 12:
            seed_summary = ", ".join(str(seed) for seed in seed_values) if seed_values else ""
        elif seed_values:
            seed_summary = (
                f"{seed_values[0]}…{seed_values[-1]} ({len(seed_values)} unique seeds per prompt)"
            )
        else:
            seed_summary = ", ".join(str(seed) for seed in record.resolved_base_seeds)
        return cls(
            batch_id=record.batch_id,
            state=state.value,
            created_at=record.created_at,
            updated_at=record.updated_at,
            seed_mode=record.seed_mode,
            variation_count=record.variation_count,
            prompts=list(record.prompts),
            prompt_summary=batch_prompt_summary(record.prompts),
            job_ids=list(record.job_ids),
            seed=record.seed,
            seed_start=record.seed_start,
            seed_end=record.seed_end,
            resolved_base_seeds=list(record.resolved_base_seeds),
            seed_summary=seed_summary,
            cancel_requested=record.cancel_requested,
            generation_profile_id=record.generation_profile_id,
            asset_type=record.asset_type,
            operation=record.operation,
            output_name=record.output_name,
            counts=BatchJobCountsSchema(**counts.to_dict()),
            progress=BatchProgressSchema(
                finished_jobs=counts.terminal,
                total_jobs=max(counts.total, len(record.job_ids)),
                completed_jobs=counts.completed,
            ),
            request=dict(record.request_template),
            jobs=[JobResponse.from_record(job) for job in jobs] if include_jobs else [],
        )


class BatchListResponse(BaseModel):
    """Recent batches for recovery and history views."""

    batches: list[BatchResponse]
    total: int
    limit: int
    offset: int


def preview_from_plan(plan: BatchExpansionPlan) -> BatchPreviewResponse:
    """Map an expansion plan to the public preview schema."""
    from unity_ai_assets.domain.jobs import prompt_summary

    return BatchPreviewResponse(
        job_count=plan.job_count,
        prompt_count=plan.prompt_count,
        variation_count=plan.variation_count,
        seed_mode=plan.seed_mode,
        base_seeds=list(plan.base_seeds),
        seed_summary=plan.seed_summary(),
        warnings=list(plan.warnings),
        items=[
            BatchExpansionItemSchema(
                index=item.index,
                prompt_index=item.prompt_index,
                variation_index=item.variation_index,
                seed=item.seed,
                prompt=item.prompt,
                prompt_summary=prompt_summary(item.prompt),
                output_name=item.output_name,
            )
            for item in plan.items
        ],
    )


__all__ = [
    "BatchJobCountsSchema",
    "BatchListResponse",
    "BatchPreviewResponse",
    "BatchProgressSchema",
    "BatchResponse",
    "BatchSubmitRequest",
    "preview_from_plan",
]
