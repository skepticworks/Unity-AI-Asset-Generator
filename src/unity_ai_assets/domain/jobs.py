"""Domain models for the local generation job system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from unity_ai_assets.core.version import JOB_RECORD_SCHEMA_VERSION
from unity_ai_assets.domain.enums import (
    JOB_CANCELLABLE_STATES,
    JOB_RETRYABLE_STATES,
    JOB_TERMINAL_STATES,
    JobProgressStage,
    JobState,
)

ALLOWED_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.RUNNING, JobState.CANCELLED}),
    JobState.RUNNING: frozenset(
        {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLING, JobState.INTERRUPTED}
    ),
    JobState.CANCELLING: frozenset({JobState.CANCELLED, JobState.FAILED, JobState.INTERRUPTED}),
    JobState.FAILED: frozenset({JobState.QUEUED}),
    JobState.INTERRUPTED: frozenset({JobState.QUEUED, JobState.FAILED}),
    JobState.CANCELLED: frozenset({JobState.QUEUED}),
    JobState.COMPLETED: frozenset(),
}

TRANSIENT_ERROR_CODES: frozenset[str] = frozenset(
    {
        "INFERENCE_FAILED",
        "MODEL_LOADING_FAILED",
        "MODEL_UNAVAILABLE",
        "OUTPUT_PERSISTENCE_FAILED",
        "BACKGROUND_REMOVAL_FAILED",
        "SEAM_INPAINT_FAILED",
        "ALPHA_PROCESSING_FAILED",
        "INTERNAL_SERVER_ERROR",
        "JOB_INTERRUPTED",
    }
)

DETERMINISTIC_ERROR_CODES: frozenset[str] = frozenset(
    {
        "GENERATION_REQUEST_INVALID",
        "REQUEST_BODY_INVALID",
        "OPERATION_UNSUPPORTED",
        "ASSET_TYPE_UNSUPPORTED",
        "SCHEDULER_UNSUPPORTED",
        "TRANSPARENCY_STRATEGY_UNSUPPORTED",
        "BACKGROUND_REMOVAL_UNAVAILABLE",
        "SEAM_INPAINT_UNAVAILABLE",
        "PIVOT_INVALID",
        "PIXELS_PER_UNIT_INVALID",
        "JOB_NOT_RETRYABLE",
        "JOB_STATE_CONFLICT",
        "JOB_NOT_CANCELLABLE",
        "JOB_CANCELLED",
    }
)


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with a trailing Z."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_retryable_error_code(code: str | None) -> bool:
    """Return whether an error code is eligible for conservative retry."""
    if not code:
        return False
    if code in DETERMINISTIC_ERROR_CODES:
        return False
    return code in TRANSIENT_ERROR_CODES


def prompt_summary(prompt: str, *, limit: int = 80) -> str:
    """Compact prompt preview for history listings (no image payloads)."""
    text = " ".join(prompt.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


@dataclass(frozen=True, slots=True)
class JobProgress:
    """Coarse progress. Percentages are omitted unless a pipeline reports real steps."""

    stage: str = JobProgressStage.QUEUED.value
    message: str = "Queued"
    current_step: int | None = None
    total_steps: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stage": self.stage,
            "message": self.message,
        }
        if self.current_step is not None:
            payload["current_step"] = self.current_step
        if self.total_steps is not None:
            payload["total_steps"] = self.total_steps
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> JobProgress:
        if not payload:
            return cls()
        return cls(
            stage=str(payload.get("stage") or JobProgressStage.QUEUED.value),
            message=str(payload.get("message") or "Queued"),
            current_step=payload.get("current_step"),
            total_steps=payload.get("total_steps"),
        )


@dataclass(frozen=True, slots=True)
class JobError:
    """Structured failure recorded on a job and in retry history."""

    code: str
    message: str
    retryable: bool
    occurred_at: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "occurred_at": self.occurred_at,
        }
        if self.details:
            payload["details"] = self.details
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> JobError:
        return cls(
            code=str(payload["code"]),
            message=str(payload.get("message") or ""),
            retryable=bool(payload.get("retryable", False)),
            occurred_at=str(payload.get("occurred_at") or utc_now_iso()),
            details=payload.get("details") if isinstance(payload.get("details"), dict) else None,
        )


@dataclass(frozen=True, slots=True)
class JobResult:
    """Completed generation metadata (not pixel data)."""

    generation_id: str
    status: str
    operation: str
    asset_type: str
    seed: int
    width: int
    height: int
    elapsed_seconds: float
    resources: dict[str, str]
    schema_versions: dict[str, str]
    image_path: str | None = None
    metadata_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "generation_id": self.generation_id,
            "status": self.status,
            "operation": self.operation,
            "asset_type": self.asset_type,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "elapsed_seconds": self.elapsed_seconds,
            "resources": dict(self.resources),
            "schema_versions": dict(self.schema_versions),
        }
        if self.image_path is not None:
            payload["image_path"] = self.image_path
        if self.metadata_path is not None:
            payload["metadata_path"] = self.metadata_path
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> JobResult:
        resources = payload.get("resources") or {}
        schema_versions = payload.get("schema_versions") or {}
        return cls(
            generation_id=str(payload["generation_id"]),
            status=str(payload.get("status") or "completed"),
            operation=str(payload.get("operation") or "text_to_image"),
            asset_type=str(payload.get("asset_type") or "texture"),
            seed=int(payload.get("seed") or 0),
            width=int(payload.get("width") or 0),
            height=int(payload.get("height") or 0),
            elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
            resources={str(k): str(v) for k, v in resources.items()},
            schema_versions={str(k): str(v) for k, v in schema_versions.items()},
            image_path=payload.get("image_path"),
            metadata_path=payload.get("metadata_path"),
        )


@dataclass
class JobRecord:
    """Persistent generation job. Request pixels stay in ``request`` only."""

    job_id: str
    state: JobState
    generation_type: str
    asset_type: str
    request: dict[str, Any]
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: JobProgress = field(default_factory=JobProgress)
    result: JobResult | None = None
    error: JobError | None = None
    retry_count: int = 0
    max_retries: int = 2
    retry_history: list[JobError] = field(default_factory=list)
    cancel_requested: bool = False
    worker_id: str | None = None
    prompt_summary: str = ""
    seed: int | None = None
    schema_version: str = JOB_RECORD_SCHEMA_VERSION

    @property
    def is_terminal(self) -> bool:
        return self.state.value in JOB_TERMINAL_STATES

    @property
    def is_cancellable(self) -> bool:
        return self.state.value in JOB_CANCELLABLE_STATES

    @property
    def is_retryable(self) -> bool:
        if self.state.value not in JOB_RETRYABLE_STATES:
            return False
        if self.retry_count >= self.max_retries:
            return False
        return self.error is None or self.error.retryable

    def can_transition_to(self, target: JobState) -> bool:
        return target in ALLOWED_TRANSITIONS.get(self.state, frozenset())

    def public_request(self) -> dict[str, Any]:
        """Request parameters with bulky image payloads removed."""
        payload = dict(self.request)
        for key in ("source_image", "mask_image"):
            value = payload.get(key)
            if isinstance(value, dict):
                redacted = {
                    k: v for k, v in value.items() if k != "content_base64" and v is not None
                }
                redacted["present"] = bool(value.get("content_base64"))
                payload[key] = redacted
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "state": self.state.value,
            "generation_type": self.generation_type,
            "asset_type": self.asset_type,
            "request": self.request,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress.to_dict(),
            "result": None if self.result is None else self.result.to_dict(),
            "error": None if self.error is None else self.error.to_dict(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "retry_history": [item.to_dict() for item in self.retry_history],
            "cancel_requested": self.cancel_requested,
            "worker_id": self.worker_id,
            "prompt_summary": self.prompt_summary,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> JobRecord:
        history_raw = payload.get("retry_history") or []
        result_raw = payload.get("result")
        error_raw = payload.get("error")
        return cls(
            job_id=str(payload["job_id"]),
            state=JobState(str(payload["state"])),
            generation_type=str(payload.get("generation_type") or "text_to_image"),
            asset_type=str(payload.get("asset_type") or "texture"),
            request=dict(payload.get("request") or {}),
            created_at=str(payload.get("created_at") or utc_now_iso()),
            updated_at=str(payload.get("updated_at") or utc_now_iso()),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            progress=JobProgress.from_dict(payload.get("progress")),
            result=None if not result_raw else JobResult.from_dict(result_raw),
            error=None if not error_raw else JobError.from_dict(error_raw),
            retry_count=int(payload.get("retry_count", 0) or 0),
            max_retries=int(payload["max_retries"]) if "max_retries" in payload else 2,
            retry_history=[
                JobError.from_dict(item) for item in history_raw if isinstance(item, dict)
            ],
            cancel_requested=bool(payload.get("cancel_requested", False)),
            worker_id=payload.get("worker_id"),
            prompt_summary=str(payload.get("prompt_summary") or ""),
            seed=payload.get("seed"),
            schema_version=str(payload.get("schema_version") or JOB_RECORD_SCHEMA_VERSION),
        )
