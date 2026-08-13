"""Batch orchestration endpoints over the existing job system."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, status

from unity_ai_assets.api.schemas.batches import (
    BatchListResponse,
    BatchPreviewResponse,
    BatchResponse,
    BatchSubmitRequest,
    preview_from_plan,
)
from unity_ai_assets.services.batch_store import validate_batch_id

router = APIRouter(prefix="/api/v1", tags=["batches"])


@router.post(
    "/batches/preview",
    response_model=BatchPreviewResponse,
)
def preview_batch(payload: BatchSubmitRequest, request: Request) -> BatchPreviewResponse:
    """Expand prompts, seeds, and variations without creating jobs."""
    batch_service = request.app.state.batch_service
    plan = batch_service.preview(
        prompts=payload.prompts,
        seed_mode=payload.seed_mode,
        variation_count=payload.variation_count,
        seed=payload.seed,
        seed_start=payload.seed_start,
        seed_end=payload.seed_end,
        output_name=payload.request.output_name,
    )
    return preview_from_plan(plan)


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_batch(payload: BatchSubmitRequest, request: Request) -> BatchResponse:
    """Expand the batch into normal jobs and enqueue them on the existing queue."""
    batch_service = request.app.state.batch_service
    record, jobs, _plan = batch_service.submit(
        prompts=payload.prompts,
        seed_mode=payload.seed_mode,
        variation_count=payload.variation_count,
        request=payload.request.model_dump(mode="json"),
        seed=payload.seed,
        seed_start=payload.seed_start,
        seed_end=payload.seed_end,
    )
    _, jobs, state, counts = batch_service.get(record.batch_id)
    return BatchResponse.from_record(record, jobs, state, counts)


@router.get("/batches", response_model=BatchListResponse)
def list_batches(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> BatchListResponse:
    """List recent batches reconstructed from persisted records."""
    batch_service = request.app.state.batch_service
    items, total = batch_service.list_batches(limit=limit, offset=offset)
    return BatchListResponse(
        batches=[
            BatchResponse.from_record(record, jobs, state, counts, include_jobs=False)
            for record, jobs, state, counts in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/batches/{batch_id}", response_model=BatchResponse)
def get_batch(batch_id: str, request: Request) -> BatchResponse:
    """Return aggregated batch state and member jobs."""
    validate_batch_id(batch_id)
    record, jobs, state, counts = request.app.state.batch_service.get(batch_id)
    return BatchResponse.from_record(record, jobs, state, counts)


@router.post("/batches/{batch_id}/cancel", response_model=BatchResponse)
def cancel_batch(batch_id: str, request: Request) -> BatchResponse:
    """Cancel eligible queued/running jobs. Completed jobs are unchanged."""
    validate_batch_id(batch_id)
    record, jobs, state, counts = request.app.state.batch_service.cancel(batch_id)
    return BatchResponse.from_record(record, jobs, state, counts)


@router.post(
    "/batches/{batch_id}/retry-failed",
    response_model=BatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_failed_batch(batch_id: str, request: Request) -> BatchResponse:
    """Retry eligible failed, interrupted, or cancelled jobs in the batch."""
    validate_batch_id(batch_id)
    record, jobs, state, counts = request.app.state.batch_service.retry_failed(batch_id)
    return BatchResponse.from_record(record, jobs, state, counts)
