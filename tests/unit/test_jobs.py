"""Unit tests for the local generation job system."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import (
    GenerationRequestInvalidError,
    JobNotCancellableError,
    JobNotRetryableError,
    JobStateConflictError,
)
from unity_ai_assets.domain.enums import JobState
from unity_ai_assets.domain.jobs import (
    JobError,
    JobProgress,
    JobRecord,
    JobResult,
    is_retryable_error_code,
    prompt_summary,
    utc_now_iso,
)
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.services.generation_service import GenerationService
from unity_ai_assets.services.job_executor import LocalGenerationExecutor
from unity_ai_assets.services.job_service import JobService
from unity_ai_assets.services.job_store import JobStore
from unity_ai_assets.services.output_service import OutputService


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    output = tmp_path / "generated"
    output.mkdir(exist_ok=True)
    values: dict[str, object] = {
        "model_id": "fake/test-model",
        "device": "cpu",
        "output_directory": output,
        "model_storage_directory": tmp_path / "models",
        "max_width": 1024,
        "max_height": 1024,
        "job_auto_retry": False,
        "max_job_retries": 2,
        "max_concurrent_generations": 1,
        "log_level": "WARNING",
        "app_version": "0.9.0-test",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _service(
    tmp_path: Path,
    backend: FakeImageGenerationBackend | None = None,
    **setting_overrides: object,
) -> tuple[JobService, FakeImageGenerationBackend]:
    settings = _settings(tmp_path, **setting_overrides)
    resolved_backend = backend or FakeImageGenerationBackend(delay_seconds=0.01)
    output = OutputService(
        settings.output_directory,
        app_version="0.9.0-test",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    generation = GenerationService(resolved_backend, output, settings)
    store = JobStore(settings.job_directory or (settings.output_directory / "jobs"))
    service = JobService(store, LocalGenerationExecutor(generation), settings)
    return service, resolved_backend


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "prompt": "rusted metal wall",
        "negative_prompt": "photo",
        "width": 32,
        "height": 32,
        "steps": 4,
        "guidance_scale": 7.0,
        "seed": 7,
        "output_name": "wall",
        "asset_type": "texture",
        "operation": "text_to_image",
    }
    body.update(overrides)
    return body


def test_job_state_machine_allows_only_defined_transitions() -> None:
    record = JobRecord(
        job_id="11111111-1111-1111-1111-111111111111",
        state=JobState.QUEUED,
        generation_type="text_to_image",
        asset_type="texture",
        request=_payload(),
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    assert record.can_transition_to(JobState.RUNNING)
    assert record.can_transition_to(JobState.CANCELLED)
    assert not record.can_transition_to(JobState.COMPLETED)
    record.state = JobState.RUNNING
    assert record.can_transition_to(JobState.COMPLETED)
    assert record.can_transition_to(JobState.FAILED)
    assert record.can_transition_to(JobState.CANCELLING)
    assert not record.can_transition_to(JobState.QUEUED)
    record.state = JobState.COMPLETED
    assert not record.can_transition_to(JobState.QUEUED)
    assert not record.can_transition_to(JobState.RUNNING)
    record.state = JobState.FAILED
    assert record.can_transition_to(JobState.QUEUED)
    record.state = JobState.CANCELLED
    assert record.can_transition_to(JobState.QUEUED)


def test_retryable_error_policy() -> None:
    assert is_retryable_error_code("INFERENCE_FAILED")
    assert is_retryable_error_code("JOB_INTERRUPTED")
    assert not is_retryable_error_code("GENERATION_REQUEST_INVALID")
    assert not is_retryable_error_code("OPERATION_UNSUPPORTED")
    assert not is_retryable_error_code("JOB_CANCELLED")


def test_job_history_round_trip_omits_image_bytes() -> None:
    record = JobRecord(
        job_id="22222222-2222-2222-2222-222222222222",
        state=JobState.COMPLETED,
        generation_type="image_to_image",
        asset_type="texture",
        request={
            "prompt": "weathered variation of a rusted plate",
            "operation": "image_to_image",
            "source_image": {"content_base64": "QUJD", "media_type": "image/png"},
            "mask_image": {"content_base64": "MASK", "media_type": "image/png"},
        },
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:01Z",
        progress=JobProgress(stage="completed", message="done"),
        result=JobResult(
            generation_id="33333333-3333-3333-3333-333333333333",
            status="completed",
            operation="image_to_image",
            asset_type="texture",
            seed=9,
            width=32,
            height=32,
            elapsed_seconds=0.1,
            resources={"image": "/i", "manifest": "/m"},
            schema_versions={"generation_manifest": "1.5"},
        ),
        error=None,
        retry_history=[
            JobError(
                code="INFERENCE_FAILED",
                message="temporary",
                retryable=True,
                occurred_at="2026-01-01T00:00:00Z",
            )
        ],
        prompt_summary=prompt_summary("weathered variation of a rusted plate"),
        seed=9,
    )
    restored = JobRecord.from_dict(json.loads(json.dumps(record.to_dict())))
    assert restored.job_id == record.job_id
    assert restored.result is not None
    assert restored.result.generation_id == record.result.generation_id
    assert restored.retry_history[0].code == "INFERENCE_FAILED"
    public = restored.public_request()
    assert "content_base64" not in public["source_image"]
    assert public["source_image"]["present"] is True
    assert public["mask_image"]["present"] is True


def test_job_record_preserves_zero_max_retries() -> None:
    record = JobRecord(
        job_id="88888888-8888-8888-8888-888888888888",
        state=JobState.INTERRUPTED,
        generation_type="text_to_image",
        asset_type="texture",
        request=_payload(),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        retry_count=0,
        max_retries=0,
    )
    restored = JobRecord.from_dict(record.to_dict())
    assert restored.max_retries == 0
    assert restored.retry_count == 0


def test_job_store_persists_and_reloads(tmp_path: Path) -> None:
    directory = tmp_path / "jobs"
    store = JobStore(directory)
    record = JobRecord(
        job_id="44444444-4444-4444-4444-444444444444",
        state=JobState.QUEUED,
        generation_type="text_to_image",
        asset_type="texture",
        request=_payload(),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        prompt_summary="rusted metal wall",
        seed=7,
    )
    store.save(record)
    store.enqueue(record.job_id)
    reloaded = JobStore(directory)
    loaded = reloaded.get(record.job_id)
    assert loaded.state is JobState.QUEUED
    assert loaded.seed == 7
    assert reloaded.queued_ids() == [record.job_id]


def test_queue_ordering_and_concurrent_submissions(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(delay_seconds=0.05)
    service, _ = _service(tmp_path, backend)
    service.start()
    try:
        first = service.submit(_payload(prompt="one", seed=1, output_name="one"))
        second = service.submit(_payload(prompt="two", seed=2, output_name="two"))
        third = service.submit(_payload(prompt="three", seed=3, output_name="three"))
        results = [
            service.wait_for_terminal(first.job_id, timeout=5),
            service.wait_for_terminal(second.job_id, timeout=5),
            service.wait_for_terminal(third.job_id, timeout=5),
        ]
        assert [item.state for item in results] == [JobState.COMPLETED] * 3
        started = [item.started_at or "" for item in results]
        assert started == sorted(started)
        assert [call.seed for call in backend.calls] == [1, 2, 3]
    finally:
        service.stop()


def test_failed_job_does_not_stop_queue(tmp_path: Path) -> None:
    class FlakyBackend(FakeImageGenerationBackend):
        def generate(self, request, **kwargs):  # type: ignore[no-untyped-def]
            if request.seed == 1:
                self._fail = True
            else:
                self._fail = False
            return super().generate(request, **kwargs)

    backend = FlakyBackend(delay_seconds=0.01)
    service, _ = _service(tmp_path, backend)
    service.start()
    try:
        failing = service.submit(_payload(seed=1, output_name="fail"))
        ok = service.submit(_payload(seed=2, output_name="ok"))
        failed = service.wait_for_terminal(failing.job_id, timeout=5)
        completed = service.wait_for_terminal(ok.job_id, timeout=5)
        assert failed.state is JobState.FAILED
        assert failed.error is not None
        assert failed.error.code == "INFERENCE_FAILED"
        assert completed.state is JobState.COMPLETED
        assert completed.result is not None
    finally:
        service.stop()


def test_cancel_queued_job(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(delay_seconds=0.2)
    service, _ = _service(tmp_path, backend)
    service.start()
    try:
        running = service.submit(_payload(seed=1, output_name="run"))
        queued = service.submit(_payload(seed=2, output_name="queued"))
        cancelled = service.cancel(queued.job_id)
        assert cancelled.state is JobState.CANCELLED
        still = service.wait_for_terminal(running.job_id, timeout=5)
        assert still.state is JobState.COMPLETED
        assert queued.job_id not in service.store.queued_ids()
    finally:
        service.stop()


def test_cancel_running_job(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(delay_seconds=0.6)
    service, _ = _service(tmp_path, backend)
    service.start()
    try:
        record = service.submit(_payload(seed=3, steps=20, output_name="slow"))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            current = service.get(record.job_id)
            if current.state is JobState.RUNNING:
                break
            time.sleep(0.01)
        cancelled = service.cancel(record.job_id)
        assert cancelled.state in {JobState.CANCELLING, JobState.CANCELLED}
        terminal = service.wait_for_terminal(record.job_id, timeout=5)
        assert terminal.state is JobState.CANCELLED
        assert terminal.result is None
    finally:
        service.stop()


def test_retry_limits_and_non_retryable(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(fail=True, delay_seconds=0.01)
    service, _ = _service(tmp_path, backend, max_job_retries=1)
    service.start()
    try:
        record = service.submit(_payload(seed=4, output_name="retry"))
        failed = service.wait_for_terminal(record.job_id, timeout=5)
        assert failed.state is JobState.FAILED
        retried = service.retry(failed.job_id)
        assert retried.state is JobState.QUEUED
        assert retried.retry_count == 1
        assert retried.result is None
        failed_again = service.wait_for_terminal(retried.job_id, timeout=5)
        assert failed_again.state is JobState.FAILED
        assert failed_again.retry_count == 1
        with pytest.raises(JobNotRetryableError):
            service.retry(failed_again.job_id)
    finally:
        service.stop()


def test_invalid_state_transitions(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    service.start()
    try:
        record = service.submit(_payload(seed=5, output_name="done"))
        completed = service.wait_for_terminal(record.job_id, timeout=5)
        assert completed.state is JobState.COMPLETED
        with pytest.raises(JobNotCancellableError):
            service.cancel(completed.job_id)
        with pytest.raises(JobStateConflictError):
            service.retry(completed.job_id)
    finally:
        service.stop()


def test_validation_failure_is_not_queued(tmp_path: Path) -> None:
    service, backend = _service(tmp_path)
    service.start()
    try:
        with pytest.raises(GenerationRequestInvalidError):
            service.submit(_payload(width=500, height=512))
        assert backend.calls == []
        assert service.list_jobs()[1] == 0
    finally:
        service.stop()


def test_restart_recovery_requeues_running_jobs(tmp_path: Path) -> None:
    settings = _settings(tmp_path, max_job_retries=2)
    store = JobStore(settings.job_directory or (settings.output_directory / "jobs"))
    running = JobRecord(
        job_id="55555555-5555-5555-5555-555555555555",
        state=JobState.RUNNING,
        generation_type="text_to_image",
        asset_type="texture",
        request=_payload(),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:01Z",
        started_at="2026-01-01T00:00:01Z",
        worker_id="dead-worker",
        seed=7,
        max_retries=2,
        retry_count=0,
    )
    queued = JobRecord(
        job_id="66666666-6666-6666-6666-666666666666",
        state=JobState.QUEUED,
        generation_type="text_to_image",
        asset_type="texture",
        request=_payload(seed=8, output_name="queued"),
        created_at="2026-01-01T00:00:02Z",
        updated_at="2026-01-01T00:00:02Z",
        seed=8,
        max_retries=2,
    )
    store.save(running)
    store.save(queued)
    backend = FakeImageGenerationBackend(delay_seconds=0.01)
    output = OutputService(
        settings.output_directory,
        app_version="0.9.0-test",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    generation = GenerationService(backend, output, settings)
    service = JobService(store, LocalGenerationExecutor(generation), settings)
    service.start()
    try:
        recovered = service.wait_for_terminal(running.job_id, timeout=5)
        other = service.wait_for_terminal(queued.job_id, timeout=5)
        assert recovered.state is JobState.COMPLETED
        assert recovered.retry_count == 1
        assert recovered.retry_history[0].code == "JOB_INTERRUPTED"
        assert other.state is JobState.COMPLETED
        assert {call.seed for call in backend.calls} == {7, 8}
    finally:
        service.stop()


def test_restart_recovery_does_not_double_claim(tmp_path: Path) -> None:
    settings = _settings(tmp_path, max_job_retries=0)
    store = JobStore(settings.job_directory or (settings.output_directory / "jobs"))
    running = JobRecord(
        job_id="77777777-7777-7777-7777-777777777777",
        state=JobState.RUNNING,
        generation_type="text_to_image",
        asset_type="texture",
        request=_payload(seed=11),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:01Z",
        started_at="2026-01-01T00:00:01Z",
        worker_id="dead-worker",
        seed=11,
        max_retries=0,
        retry_count=0,
    )
    store.save(running)
    backend = FakeImageGenerationBackend(delay_seconds=0.01)
    output = OutputService(
        settings.output_directory,
        app_version="0.9.0-test",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    service = JobService(
        store,
        LocalGenerationExecutor(GenerationService(backend, output, settings)),
        settings,
    )
    service.start()
    try:
        recovered = service.get(running.job_id)
        assert recovered.state is JobState.INTERRUPTED
        assert recovered.error is not None
        assert recovered.error.code == "JOB_INTERRUPTED"
        time.sleep(0.05)
        assert backend.calls == []
    finally:
        service.stop()


def test_shutdown_rejects_new_work(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    service.start()
    service.stop()
    from unity_ai_assets.core.errors import JobServiceUnavailableError

    with pytest.raises(JobServiceUnavailableError):
        service.submit(_payload())


def test_thread_safe_progress_updates(tmp_path: Path) -> None:
    service, _ = _service(tmp_path, FakeImageGenerationBackend(delay_seconds=0.1))
    service.start()
    try:
        record = service.submit(_payload(steps=8, output_name="progress"))
        seen_running = False
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            current = service.get(record.job_id)
            if current.state is JobState.RUNNING:
                seen_running = True
                break
            time.sleep(0.01)
        terminal = service.wait_for_terminal(record.job_id, timeout=5)
        assert seen_running
        assert terminal.state is JobState.COMPLETED
        assert terminal.progress.stage == "completed"
    finally:
        service.stop()


def test_prompt_summary_is_compact() -> None:
    assert prompt_summary("short") == "short"
    long_prompt = "word " * 40
    summary = prompt_summary(long_prompt, limit=20)
    assert len(summary) <= 20
    assert summary.endswith("…")
