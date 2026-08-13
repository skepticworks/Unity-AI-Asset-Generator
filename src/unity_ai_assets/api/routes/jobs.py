"""Local generation job endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, status

from unity_ai_assets.api.schemas.generation import TextureGenerationRequest
from unity_ai_assets.api.schemas.jobs import JobListResponse, JobResponse, JobResultSchema
from unity_ai_assets.core.errors import JobStateConflictError
from unity_ai_assets.domain.enums import JobState
from unity_ai_assets.services.job_store import validate_job_id

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_job(payload: TextureGenerationRequest, request: Request) -> JobResponse:
    """Queue a generation job. GPU work runs on the local worker, not this request."""
    job_service = request.app.state.job_service
    record = job_service.submit(payload.model_dump(mode="json"))
    return JobResponse.from_record(record)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    request: Request,
    state: JobState | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    """List recent generation jobs for history views."""
    job_service = request.app.state.job_service
    settings = request.app.state.settings
    resolved_limit = min(limit, int(settings.job_history_limit))
    records, total = job_service.list_jobs(state=state, limit=resolved_limit, offset=offset)
    return JobListResponse(
        jobs=[JobResponse.from_record(item) for item in records],
        total=total,
        limit=resolved_limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, request: Request) -> JobResponse:
    """Return job status, coarse progress, and any result or error."""
    validate_job_id(job_id)
    record = request.app.state.job_service.get(job_id)
    return JobResponse.from_record(record)


@router.get("/jobs/{job_id}/result", response_model=JobResultSchema)
def get_job_result(job_id: str, request: Request) -> JobResultSchema:
    """Return completed result metadata. Fails if the job is not completed."""
    validate_job_id(job_id)
    record = request.app.state.job_service.get(job_id)
    response = JobResponse.from_record(record)
    if record.state is not JobState.COMPLETED or response.result is None:
        raise JobStateConflictError(
            f"Job '{job_id}' has no completed result (state={record.state.value})."
        )
    return response.result


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, request: Request) -> JobResponse:
    """Cancel a queued job immediately, or a running job at the next safe point."""
    validate_job_id(job_id)
    record = request.app.state.job_service.cancel(job_id)
    return JobResponse.from_record(record)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_job(job_id: str, request: Request) -> JobResponse:
    """Requeue an eligible failed, interrupted, or cancelled job."""
    validate_job_id(job_id)
    record = request.app.state.job_service.retry(job_id)
    return JobResponse.from_record(record)
