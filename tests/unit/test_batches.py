"""Unit tests for batch orchestration over the persistent job system."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import BatchNotFoundError, BatchTooLargeError
from unity_ai_assets.domain.enums import BatchState, JobState
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.services.batch_service import BatchService
from unity_ai_assets.services.batch_store import BatchStore
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
        "max_width": 1024,
        "max_height": 1024,
        "job_auto_retry": False,
        "max_job_retries": 2,
        "max_concurrent_generations": 1,
        "max_batch_jobs": 16,
        "log_level": "WARNING",
        "app_version": "0.10.0-test",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _services(
    tmp_path: Path,
    backend: FakeImageGenerationBackend | None = None,
    **setting_overrides: object,
) -> tuple[BatchService, JobService, FakeImageGenerationBackend]:
    settings = _settings(tmp_path, **setting_overrides)
    resolved_backend = backend or FakeImageGenerationBackend(delay_seconds=0.01)
    output = OutputService(
        settings.output_directory,
        app_version="0.10.0-test",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    generation = GenerationService(resolved_backend, output, settings)
    job_store = JobStore(settings.job_directory or (settings.output_directory / "jobs"))
    job_service = JobService(job_store, LocalGenerationExecutor(generation), settings)
    batch_store = BatchStore(
        settings.batch_directory or (settings.output_directory / "batches")
    )
    batch_service = BatchService(batch_store, job_service, settings)
    return batch_service, job_service, resolved_backend


def _request(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "prompt": "placeholder",
        "negative_prompt": "photo",
        "width": 32,
        "height": 32,
        "steps": 2,
        "guidance_scale": 7.0,
        "output_name": "batch_tex",
        "asset_type": "texture",
        "operation": "text_to_image",
        "generation_profile_id": "ps1_environment_texture",
    }
    body.update(overrides)
    return body


def test_submit_creates_associated_jobs_in_expansion_order(tmp_path: Path) -> None:
    batches, jobs, backend = _services(tmp_path)
    jobs.start()
    try:
        record, created, plan = batches.submit(
            prompts=["alpha", "beta"],
            seed_mode="fixed",
            variation_count=2,
            request=_request(),
            seed=20,
        )
        assert plan.job_count == 4
        assert len(created) == 4
        assert [item.batch_index for item in created] == [0, 1, 2, 3]
        assert [item.seed for item in created] == [20, 21, 20, 21]
        assert all(item.batch_id == record.batch_id for item in created)
        assert created[0].prompt_index == 0
        assert created[0].variation_index == 0
        assert created[1].variation_index == 1
        assert created[2].prompt_index == 1
        listed, total = jobs.list_jobs(batch_id=record.batch_id, limit=20)
        assert total == 4
        assert {item.job_id for item in listed} == set(record.job_ids)
        for job in created:
            jobs.wait_for_terminal(job.job_id, timeout=5)
        _, finished, state, counts = batches.get(record.batch_id)
        assert state is BatchState.COMPLETED
        assert counts.completed == 4
        assert {call.seed for call in backend.calls} == {20, 21}
        assert len(finished) == 4
    finally:
        jobs.stop()


def test_partial_failure_keeps_successful_jobs(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(
        delay_seconds=0.01,
        fail_if=lambda request: "fail" in request.prompt,
    )
    batches, jobs, _ = _services(tmp_path, backend)
    jobs.start()
    try:
        record, created, _plan = batches.submit(
            prompts=["ok metal", "fail this one"],
            seed_mode="fixed",
            variation_count=1,
            request=_request(),
            seed=3,
        )
        terminals = [jobs.wait_for_terminal(item.job_id, timeout=5) for item in created]
        states = {item.prompt_summary: item.state for item in terminals}
        assert any(item.state is JobState.COMPLETED for item in terminals)
        assert any(item.state is JobState.FAILED for item in terminals)
        _, _members, batch_state, counts = batches.get(record.batch_id)
        assert batch_state is BatchState.PARTIAL_SUCCESS
        assert counts.completed == 1
        assert counts.failed == 1
        assert states["fail this one"] is JobState.FAILED
        successful = next(item for item in terminals if item.state is JobState.COMPLETED)
        assert successful.result is not None
        failed = next(item for item in terminals if item.state is JobState.FAILED)
        assert failed.error is not None
        assert failed.error.code == "INFERENCE_FAILED"
    finally:
        jobs.stop()


def test_batch_cancel_leaves_completed_jobs(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(delay_seconds=0.25)
    batches, jobs, _ = _services(tmp_path, backend)
    jobs.start()
    try:
        record, created, _plan = batches.submit(
            prompts=["slow one", "queued later"],
            seed_mode="fixed",
            variation_count=1,
            request=_request(steps=8),
            seed=8,
        )
        first = jobs.wait_for_terminal(created[0].job_id, timeout=5)
        assert first.state is JobState.COMPLETED
        _, _, state_before, _ = batches.get(record.batch_id)
        assert state_before in {BatchState.QUEUED, BatchState.RUNNING, BatchState.PARTIAL_SUCCESS}
        _, members, state, counts = batches.cancel(record.batch_id)
        assert first.job_id in record.job_ids
        completed = next(item for item in members if item.job_id == first.job_id)
        assert completed.state is JobState.COMPLETED
        assert completed.result is not None
        other = next(item for item in members if item.job_id != first.job_id)
        assert other.state in {JobState.CANCELLED, JobState.CANCELLING}
        if other.state is JobState.CANCELLING:
            other = jobs.wait_for_terminal(other.job_id, timeout=5)
        assert other.state is JobState.CANCELLED
        _, _, final_state, final_counts = batches.get(record.batch_id)
        assert final_state is BatchState.PARTIAL_SUCCESS
        assert final_counts.completed == 1
        assert final_counts.cancelled == 1
        assert counts.completed == 1
        assert state in {BatchState.CANCELLING, BatchState.PARTIAL_SUCCESS, BatchState.CANCELLED}
    finally:
        jobs.stop()


def test_retry_failed_requeues_only_eligible_failures(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(
        delay_seconds=0.01,
        fail_if=lambda request: "fail" in request.prompt,
    )
    batches, jobs, _ = _services(tmp_path, backend, max_job_retries=2)
    jobs.start()
    try:
        record, created, _plan = batches.submit(
            prompts=["ok", "fail"],
            seed_mode="fixed",
            variation_count=1,
            request=_request(),
            seed=4,
        )
        for item in created:
            jobs.wait_for_terminal(item.job_id, timeout=5)
        backend._fail_if = None
        _, members, state, counts = batches.retry_failed(record.batch_id)
        assert state in {
            BatchState.QUEUED,
            BatchState.RUNNING,
            BatchState.COMPLETED,
            BatchState.PARTIAL_SUCCESS,
        }
        retried = next(item for item in members if "fail" in item.prompt_summary)
        assert retried.state in {JobState.QUEUED, JobState.RUNNING, JobState.COMPLETED}
        assert retried.retry_count == 1
        succeeded = next(item for item in members if item.prompt_summary == "ok")
        assert succeeded.state is JobState.COMPLETED
        terminal = jobs.wait_for_terminal(retried.job_id, timeout=5)
        assert terminal.state is JobState.COMPLETED
        _, _, final_state, final_counts = batches.get(record.batch_id)
        assert final_state is BatchState.COMPLETED
        assert final_counts.completed == 2
        assert counts.completed >= 1
    finally:
        jobs.stop()


def test_batch_persistence_survives_store_reload(tmp_path: Path) -> None:
    batches, jobs, _ = _services(tmp_path)
    jobs.start()
    try:
        record, created, _plan = batches.submit(
            prompts=["persist me"],
            seed_mode="sequential",
            variation_count=1,
            request=_request(),
            seed_start=5,
            seed_end=6,
        )
        for item in created:
            jobs.wait_for_terminal(item.job_id, timeout=5)
        batch_id = record.batch_id
    finally:
        jobs.stop()

    restored_jobs = JobStore(
        _settings(tmp_path).job_directory or tmp_path / "generated" / "jobs"
    )
    restored_batches = BatchStore(
        _settings(tmp_path).batch_directory or tmp_path / "generated" / "batches"
    )
    settings = _settings(tmp_path)
    backend = FakeImageGenerationBackend(delay_seconds=0.01)
    output = OutputService(
        settings.output_directory,
        app_version="0.10.0-test",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    job_service = JobService(
        restored_jobs,
        LocalGenerationExecutor(GenerationService(backend, output, settings)),
        settings,
    )
    service = BatchService(restored_batches, job_service, settings)
    loaded, members, state, counts = service.get(batch_id)
    assert loaded.batch_id == batch_id
    assert len(loaded.job_ids) == 2
    assert len(members) == 2
    assert all(item.batch_id == batch_id for item in members)
    assert state is BatchState.COMPLETED
    assert counts.completed == 2
    with pytest.raises(BatchNotFoundError):
        service.get("99999999-9999-9999-9999-999999999999")


def test_excessive_batch_is_rejected_before_queueing(tmp_path: Path) -> None:
    batches, jobs, backend = _services(tmp_path, max_batch_jobs=3)
    jobs.start()
    try:
        with pytest.raises(BatchTooLargeError):
            batches.submit(
                prompts=["a", "b"],
                seed_mode="sequential",
                variation_count=2,
                request=_request(),
                seed_start=1,
                seed_end=2,
            )
        assert backend.calls == []
        assert jobs.list_jobs()[1] == 0
        assert batches.store.list_records()[1] == 0
    finally:
        jobs.stop()


def test_preview_does_not_create_jobs(tmp_path: Path) -> None:
    batches, jobs, backend = _services(tmp_path)
    jobs.start()
    try:
        plan = batches.preview(
            prompts=["one", "two"],
            seed_mode="fixed",
            variation_count=2,
            seed=1,
            output_name="tex",
        )
        assert plan.job_count == 4
        assert jobs.list_jobs()[1] == 0
        assert backend.calls == []
        time.sleep(0.02)
        assert batches.store.list_records()[1] == 0
    finally:
        jobs.stop()
