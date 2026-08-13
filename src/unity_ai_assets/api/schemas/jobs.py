"""Public API schemas for the local generation job system."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from unity_ai_assets.api.schemas.generation import (
    GenerationResources,
    GenerationSchemaVersions,
    TextureGenerationRequest,
)
from unity_ai_assets.domain.jobs import JobRecord

JobStateLiteral = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelling",
    "cancelled",
    "interrupted",
]


class JobProgressSchema(BaseModel):
    """Coarse job progress. Step counts are included only when the pipeline reports them."""

    stage: str
    message: str
    current_step: int | None = None
    total_steps: int | None = None


class JobErrorSchema(BaseModel):
    """Persisted job failure."""

    code: str
    message: str
    retryable: bool
    occurred_at: str
    details: dict[str, Any] | None = None


class JobResultSchema(BaseModel):
    """Completed generation metadata attached to a job."""

    generation_id: str
    status: str
    operation: str
    asset_type: str
    seed: int
    width: int
    height: int
    elapsed_seconds: float
    resources: GenerationResources
    schema_versions: GenerationSchemaVersions
    image_path: str | None = Field(default=None, deprecated=True)
    metadata_path: str | None = Field(default=None, deprecated=True)


class JobResponse(BaseModel):
    """Public job record. Image payloads are never returned."""

    job_id: str
    state: JobStateLiteral
    generation_type: str
    asset_type: str
    prompt_summary: str
    seed: int | None = None
    batch_id: str | None = None
    batch_index: int | None = None
    prompt_index: int | None = None
    variation_index: int | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: JobProgressSchema
    result: JobResultSchema | None = None
    error: JobErrorSchema | None = None
    retry_count: int
    max_retries: int
    retry_history: list[JobErrorSchema] = Field(default_factory=list)
    cancel_requested: bool = False
    request: dict[str, Any] = Field(
        default_factory=dict,
        description="Submitted parameters with bulky image bytes omitted",
    )

    @classmethod
    def from_record(cls, record: JobRecord) -> JobResponse:
        result = None
        if record.result is not None:
            resources = record.result.resources
            result = JobResultSchema(
                generation_id=record.result.generation_id,
                status=record.result.status,
                operation=record.result.operation,
                asset_type=record.result.asset_type,
                seed=record.result.seed,
                width=record.result.width,
                height=record.result.height,
                elapsed_seconds=record.result.elapsed_seconds,
                resources=GenerationResources(
                    image=resources.get(
                        "image",
                        f"/api/v1/generations/{record.result.generation_id}/image",
                    ),
                    manifest=resources.get(
                        "manifest",
                        f"/api/v1/generations/{record.result.generation_id}/manifest",
                    ),
                ),
                schema_versions=GenerationSchemaVersions(
                    generation_manifest=record.result.schema_versions.get(
                        "generation_manifest", "1.5"
                    )
                ),
                image_path=record.result.image_path,
                metadata_path=record.result.metadata_path,
            )
        progress = JobProgressSchema(
            stage=record.progress.stage,
            message=record.progress.message,
            current_step=record.progress.current_step,
            total_steps=record.progress.total_steps,
        )
        error = None if record.error is None else JobErrorSchema(**record.error.to_dict())
        history = [JobErrorSchema(**item.to_dict()) for item in record.retry_history]
        return cls(
            job_id=record.job_id,
            state=record.state.value,
            generation_type=record.generation_type,
            asset_type=record.asset_type,
            prompt_summary=record.prompt_summary,
            seed=record.seed,
            batch_id=record.batch_id,
            batch_index=record.batch_index,
            prompt_index=record.prompt_index,
            variation_index=record.variation_index,
            created_at=record.created_at,
            updated_at=record.updated_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            progress=progress,
            result=result,
            error=error,
            retry_count=record.retry_count,
            max_retries=record.max_retries,
            retry_history=history,
            cancel_requested=record.cancel_requested,
            request=record.public_request(),
        )


class JobListResponse(BaseModel):
    """Paginated generation history."""

    jobs: list[JobResponse]
    total: int
    limit: int
    offset: int


class JobSubmitRequest(TextureGenerationRequest):
    """Submit body is the existing texture generation request."""


__all__ = [
    "JobErrorSchema",
    "JobListResponse",
    "JobProgressSchema",
    "JobResponse",
    "JobResultSchema",
    "JobSubmitRequest",
]
