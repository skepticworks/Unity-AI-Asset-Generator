"""Local job queue, worker loop, cancellation, retry, and restart recovery."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import (
    AppError,
    GenerationCancelledError,
    JobCancelledError,
    JobNotCancellableError,
    JobNotRetryableError,
    JobServiceUnavailableError,
    JobStateConflictError,
)
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.enums import JOB_ACTIVE_STATES, JobProgressStage, JobState
from unity_ai_assets.domain.jobs import (
    JobError,
    JobProgress,
    JobRecord,
    JobResult,
    is_retryable_error_code,
    prompt_summary,
    utc_now_iso,
)
from unity_ai_assets.services.job_executor import GenerationJobExecutor
from unity_ai_assets.services.job_store import JobStore, validate_job_id

logger = get_logger(__name__)


def _error_from_exception(exc: BaseException) -> JobError:
    if isinstance(exc, AppError):
        code = exc.code.value
        details = exc.details_payload()
        return JobError(
            code=code,
            message=exc.message,
            retryable=is_retryable_error_code(code),
            occurred_at=utc_now_iso(),
            details=details,
        )
    return JobError(
        code=AppErrorCode.INTERNAL_SERVER_ERROR.value,
        message="An unexpected server error occurred.",
        retryable=True,
        occurred_at=utc_now_iso(),
        details={"exception_type": type(exc).__name__},
    )


class JobService:
    """Owns job state, the FIFO queue, and GPU worker threads.

    Execution backends are injected so a future remote worker can replace the
    local GPU executor without changing the API or Unity client.
    """

    def __init__(
        self,
        store: JobStore,
        executor: GenerationJobExecutor,
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        self._store = store
        self._executor = executor
        self._settings = settings
        self._worker_id = worker_id or uuid.uuid4().hex
        self._max_retries = int(settings.max_job_retries)
        self._auto_retry = bool(settings.job_auto_retry)
        self._worker_count = max(1, int(settings.max_concurrent_generations))
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._cancel_events: dict[str, threading.Event] = {}
        self._accepting = False
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._busy = 0

    @property
    def store(self) -> JobStore:
        return self._store

    @property
    def accepting(self) -> bool:
        return self._accepting

    def start(self) -> None:
        """Recover persisted jobs and start worker threads."""
        with self._lock:
            if self._accepting:
                return
            self._stop.clear()
            self._recover_locked()
            self._accepting = True
            self._threads = []
            for index in range(self._worker_count):
                thread = threading.Thread(
                    target=self._worker_loop,
                    name=f"generation-job-worker-{index}",
                    daemon=True,
                )
                self._threads.append(thread)
                thread.start()
        logger.info(
            "Job service started workers=%s persistence=%s auto_retry=%s max_retries=%s",
            self._worker_count,
            self._store.directory,
            self._auto_retry,
            self._max_retries,
        )

    def stop(self, *, timeout: float = 15.0) -> None:
        """Stop accepting work and join workers. In-flight jobs finish or recover later."""
        with self._lock:
            self._accepting = False
            self._stop.set()
            self._condition.notify_all()
        deadline = time.monotonic() + timeout
        for thread in list(self._threads):
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)
        self._threads.clear()
        logger.info("Job service stopped")

    def submit(
        self,
        payload: dict[str, Any],
        *,
        batch_id: str | None = None,
        batch_index: int | None = None,
        prompt_index: int | None = None,
        variation_index: int | None = None,
    ) -> JobRecord:
        """Validate, persist, and enqueue a generation job."""
        with self._lock:
            if not self._accepting:
                raise JobServiceUnavailableError(
                    "The job service is shutting down and is not accepting new work."
                )
        resolved_seed = self._executor.validate(payload)
        stored_payload = dict(payload)
        stored_payload["seed"] = resolved_seed
        now = utc_now_iso()
        record = JobRecord(
            job_id=str(uuid.uuid4()),
            state=JobState.QUEUED,
            generation_type=str(payload.get("operation") or "text_to_image"),
            asset_type=str(payload.get("asset_type") or "texture"),
            request=stored_payload,
            created_at=now,
            updated_at=now,
            progress=JobProgress(
                stage=JobProgressStage.QUEUED.value,
                message="Queued for generation",
            ),
            retry_count=0,
            max_retries=self._max_retries,
            prompt_summary=prompt_summary(str(payload.get("prompt") or "")),
            seed=resolved_seed,
            batch_id=batch_id,
            batch_index=batch_index,
            prompt_index=prompt_index,
            variation_index=variation_index,
        )
        with self._lock:
            if not self._accepting:
                raise JobServiceUnavailableError(
                    "The job service is shutting down and is not accepting new work."
                )
            self._store.save(record)
            self._store.enqueue(record.job_id)
            self._condition.notify()
        logger.info(
            "Queued job_id=%s operation=%s seed=%s",
            record.job_id,
            record.generation_type,
            resolved_seed,
        )
        return record

    def get(self, job_id: str) -> JobRecord:
        return self._store.get(validate_job_id(job_id))

    def list_jobs(
        self,
        *,
        state: JobState | None = None,
        batch_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[JobRecord], int]:
        return self._store.list_records(
            state=state, batch_id=batch_id, limit=limit, offset=offset
        )

    def has_active_jobs(self) -> bool:
        """True when any job is queued, running, or cancelling."""
        with self._lock:
            if self._busy > 0:
                return True
        return any(record.state.value in JOB_ACTIVE_STATES for record in self._store.all_records())

    def cancel(self, job_id: str) -> JobRecord:
        job_id = validate_job_id(job_id)
        with self._lock:
            record = self._store.get(job_id)
            if not record.is_cancellable:
                raise JobNotCancellableError(
                    f"Job '{job_id}' cannot be cancelled while {record.state.value}."
                )
            record.cancel_requested = True
            record.updated_at = utc_now_iso()
            if record.state is JobState.QUEUED:
                self._store.remove_from_queue(job_id)
                record.state = JobState.CANCELLED
                record.completed_at = record.updated_at
                record.progress = JobProgress(
                    stage=JobProgressStage.CANCELLED.value,
                    message="Cancelled before execution",
                )
                record.error = JobError(
                    code=AppErrorCode.JOB_CANCELLED.value,
                    message="Job cancelled while queued.",
                    retryable=True,
                    occurred_at=record.updated_at,
                )
                self._store.save(record)
                self._condition.notify_all()
                return record
            record.state = JobState.CANCELLING
            record.progress = JobProgress(
                stage=JobProgressStage.CANCELLING.value,
                message="Cancellation requested; stopping at the next safe point",
            )
            self._store.save(record)
            event = self._cancel_events.get(job_id)
            if event is not None:
                event.set()
            return record

    def retry(self, job_id: str) -> JobRecord:
        job_id = validate_job_id(job_id)
        with self._lock:
            if not self._accepting:
                raise JobServiceUnavailableError(
                    "The job service is shutting down and is not accepting new work."
                )
            record = self._store.get(job_id)
            if not record.can_transition_to(JobState.QUEUED):
                raise JobStateConflictError(
                    f"Job '{job_id}' cannot be retried from state {record.state.value}."
                )
            if record.retry_count >= record.max_retries:
                raise JobNotRetryableError(
                    f"Job '{job_id}' has reached the maximum retry count "
                    f"({record.max_retries})."
                )
            if record.error is not None and not record.error.retryable:
                raise JobNotRetryableError(
                    f"Job '{job_id}' failed with a non-retryable error "
                    f"({record.error.code})."
                )
            if record.error is not None:
                record.retry_history.append(record.error)
            record.retry_count += 1
            record.state = JobState.QUEUED
            record.cancel_requested = False
            record.worker_id = None
            record.started_at = None
            record.completed_at = None
            record.result = None
            record.error = None
            record.updated_at = utc_now_iso()
            record.progress = JobProgress(
                stage=JobProgressStage.QUEUED.value,
                message=f"Queued for retry ({record.retry_count}/{record.max_retries})",
            )
            self._store.save(record)
            self._store.enqueue(record.job_id)
            self._condition.notify()
            return record

    def wait_for_terminal(self, job_id: str, *, timeout: float | None = None) -> JobRecord:
        """Block until the job reaches a terminal state (used by the sync API)."""
        job_id = validate_job_id(job_id)
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while True:
                record = self._store.get(job_id)
                if record.is_terminal:
                    return record
                remaining = None
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return record
                self._condition.wait(timeout=remaining)

    def raise_if_unsuccessful(self, record: JobRecord) -> JobResult:
        """Translate a terminal job into a result or an AppError for sync callers."""
        if record.state is JobState.COMPLETED and record.result is not None:
            return record.result
        if record.state is JobState.CANCELLED:
            raise JobCancelledError("The generation job was cancelled.")
        if record.error is not None:
            try:
                code = AppErrorCode(record.error.code)
            except ValueError:
                code = AppErrorCode.INTERNAL_SERVER_ERROR
            raise AppError(record.error.message, code=code, details=record.error.details)
        raise AppError(
            "The generation job did not complete successfully.",
            code=AppErrorCode.INTERNAL_SERVER_ERROR,
        )

    def _recover_locked(self) -> None:
        """Rebuild the queue and recover jobs left running after a process exit."""
        self._store.reload()
        recovered: list[JobRecord] = []
        for record in self._store.all_records():
            if record.state in {JobState.RUNNING, JobState.CANCELLING}:
                now = utc_now_iso()
                interrupted = JobError(
                    code=AppErrorCode.JOB_INTERRUPTED.value,
                    message=(
                        "Job was running when the backend process stopped. "
                        "The GPU result was not assumed complete."
                    ),
                    retryable=True,
                    occurred_at=now,
                )
                record.retry_history.append(interrupted)
                record.worker_id = None
                record.cancel_requested = False
                record.updated_at = now
                record.started_at = None
                record.result = None
                can_requeue = (
                    record.retry_count < record.max_retries
                    and record.state is not JobState.CANCELLING
                )
                if can_requeue:
                    record.retry_count += 1
                    record.state = JobState.QUEUED
                    record.error = None
                    record.progress = JobProgress(
                        stage=JobProgressStage.QUEUED.value,
                        message="Requeued after backend restart",
                    )
                    self._store.save(record)
                    self._store.enqueue(record.job_id)
                else:
                    record.state = JobState.INTERRUPTED
                    record.completed_at = now
                    record.error = interrupted
                    record.progress = JobProgress(
                        stage=JobProgressStage.INTERRUPTED.value,
                        message="Interrupted by backend restart",
                    )
                    self._store.save(record)
                recovered.append(record)
        queued = [
            item for item in self._store.all_records() if item.state is JobState.QUEUED
        ]
        queued.sort(key=lambda item: (item.created_at, item.job_id))
        for item in queued:
            self._store.remove_from_queue(item.job_id)
        for item in queued:
            self._store.enqueue(item.job_id)
        logger.info(
            "Job recovery scanned records recovered=%s queued=%s",
            len(recovered),
            len(queued),
        )

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            record = self._wait_for_claim()
            if record is None:
                continue
            try:
                self._run_claimed_job(record)
            except Exception:
                logger.exception(
                    "Job worker isolated an unexpected error job_id=%s", record.job_id
                )
                try:
                    self._fail_job(
                        record.job_id,
                        JobError(
                            code=AppErrorCode.INTERNAL_SERVER_ERROR.value,
                            message="The job worker encountered an unexpected error.",
                            retryable=True,
                            occurred_at=utc_now_iso(),
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Failed to persist worker isolation error job_id=%s", record.job_id
                    )
            finally:
                with self._lock:
                    self._busy = max(0, self._busy - 1)
                    self._cancel_events.pop(record.job_id, None)
                    self._condition.notify_all()

    def _wait_for_claim(self) -> JobRecord | None:
        with self._condition:
            while not self._stop.is_set():
                claimed = self._claim_next_locked()
                if claimed is not None:
                    self._busy += 1
                    return claimed
                self._condition.wait(timeout=0.25)
            return None

    def _claim_next_locked(self) -> JobRecord | None:
        while True:
            record = self._store.claim_next()
            if record is None:
                return None
            if record.cancel_requested:
                record.state = JobState.CANCELLED
                record.updated_at = utc_now_iso()
                record.completed_at = record.updated_at
                record.progress = JobProgress(
                    stage=JobProgressStage.CANCELLED.value,
                    message="Cancelled before execution",
                )
                record.error = JobError(
                    code=AppErrorCode.JOB_CANCELLED.value,
                    message="Job cancelled while queued.",
                    retryable=True,
                    occurred_at=record.updated_at,
                )
                self._store.save(record)
                continue
            if record.state is not JobState.QUEUED:
                continue
            record.state = JobState.RUNNING
            record.started_at = utc_now_iso()
            record.updated_at = record.started_at
            record.worker_id = self._worker_id
            record.progress = JobProgress(
                stage=JobProgressStage.GENERATING.value,
                message="Running generation",
            )
            self._store.save(record)
            event = threading.Event()
            self._cancel_events[record.job_id] = event
            if record.cancel_requested:
                event.set()
            return record

    def _run_claimed_job(self, record: JobRecord) -> None:
        job_id = record.job_id
        cancel_event = self._cancel_events.get(job_id) or threading.Event()

        def on_progress(progress: JobProgress) -> None:
            with self._lock:
                current = self._store.get(job_id)
                if current.state not in {JobState.RUNNING, JobState.CANCELLING}:
                    return
                current.progress = progress
                current.updated_at = utc_now_iso()
                self._store.save(current)
                self._condition.notify_all()

        try:
            result = self._executor.execute(
                record,
                cancel_event=cancel_event,
                on_progress=on_progress,
            )
        except GenerationCancelledError:
            self._mark_cancelled(job_id)
            return
        except AppError as exc:
            self._handle_failure(job_id, _error_from_exception(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job execution failed job_id=%s", job_id)
            self._handle_failure(job_id, _error_from_exception(exc))
            return

        with self._lock:
            current = self._store.get(job_id)
            if current.cancel_requested or current.state is JobState.CANCELLING:
                self._mark_cancelled_locked(current)
                return
            current.state = JobState.COMPLETED
            current.result = result
            current.error = None
            current.seed = result.seed
            current.completed_at = utc_now_iso()
            current.updated_at = current.completed_at
            current.worker_id = None
            current.progress = JobProgress(
                stage=JobProgressStage.COMPLETED.value,
                message="Generation completed",
            )
            self._store.save(current)
            self._condition.notify_all()

    def _handle_failure(self, job_id: str, error: JobError) -> None:
        with self._lock:
            record = self._store.get(job_id)
            if record.cancel_requested or record.state is JobState.CANCELLING:
                self._mark_cancelled_locked(record)
                return
            if (
                self._auto_retry
                and error.retryable
                and record.retry_count < record.max_retries
            ):
                record.retry_history.append(error)
                record.retry_count += 1
                record.state = JobState.QUEUED
                record.error = None
                record.worker_id = None
                record.started_at = None
                record.result = None
                record.updated_at = utc_now_iso()
                record.progress = JobProgress(
                    stage=JobProgressStage.QUEUED.value,
                    message=(
                        f"Retrying after {error.code} "
                        f"({record.retry_count}/{record.max_retries})"
                    ),
                )
                self._store.save(record)
                self._store.enqueue(record.job_id)
                self._condition.notify()
                return
            record.state = JobState.FAILED
            record.error = error
            record.completed_at = utc_now_iso()
            record.updated_at = record.completed_at
            record.worker_id = None
            record.progress = JobProgress(
                stage=JobProgressStage.FAILED.value,
                message=error.message,
            )
            self._store.save(record)
            self._condition.notify_all()

    def _fail_job(self, job_id: str, error: JobError) -> None:
        with self._lock:
            record = self._store.get(job_id)
            if record.is_terminal:
                return
            record.state = JobState.FAILED
            record.error = error
            record.completed_at = utc_now_iso()
            record.updated_at = record.completed_at
            record.worker_id = None
            record.progress = JobProgress(
                stage=JobProgressStage.FAILED.value,
                message=error.message,
            )
            self._store.save(record)
            self._condition.notify_all()

    def _mark_cancelled(self, job_id: str) -> None:
        with self._lock:
            self._mark_cancelled_locked(self._store.get(job_id))

    def _mark_cancelled_locked(self, record: JobRecord) -> None:
        record.state = JobState.CANCELLED
        record.cancel_requested = True
        record.completed_at = utc_now_iso()
        record.updated_at = record.completed_at
        record.worker_id = None
        record.result = None
        record.progress = JobProgress(
            stage=JobProgressStage.CANCELLED.value,
            message="Cancelled",
        )
        record.error = JobError(
            code=AppErrorCode.JOB_CANCELLED.value,
            message="Job cancelled.",
            retryable=True,
            occurred_at=record.updated_at,
        )
        self._store.save(record)
        self._condition.notify_all()
