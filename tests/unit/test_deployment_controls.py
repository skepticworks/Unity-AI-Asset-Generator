"""Tests for deployment-oriented configuration and operational controls."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import GenerationCancelledError
from unity_ai_assets.domain.enums import JobState
from unity_ai_assets.domain.jobs import JobProgress, JobRecord, JobResult, utc_now_iso
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app
from unity_ai_assets.services.job_executor import (
    RemoteGenerationExecutor,
    RemoteWorkerStatus,
    RemoteWorkerSubmission,
)
from unity_ai_assets.services.job_store import JobStore
from unity_ai_assets.services.remote_worker_http import HttpRemoteWorkerClient
from unity_ai_assets.services.runtime_validation import HardwareSnapshot, RuntimeValidator


class _Probe:
    def __init__(self, snapshot: HardwareSnapshot) -> None:
        self._snapshot = snapshot

    def snapshot(self) -> HardwareSnapshot:
        return self._snapshot


class _FakeRemoteClient:
    def __init__(self, result: JobResult, states: list[str] | None = None) -> None:
        self.submitted: list[object] = []
        self.cancelled: list[str] = []
        self._result = result
        self._states = list(states or ["completed"])

    def submit(self, submission: RemoteWorkerSubmission) -> str:
        self.submitted.append(submission)
        return submission.request_id

    def get_status(self, remote_job_id: str) -> RemoteWorkerStatus:
        state = self._states.pop(0) if self._states else "completed"
        return RemoteWorkerStatus(
            job_id=remote_job_id,
            state=state,
            progress=JobProgress(stage=state, message=state),
            result=self._result if state == "completed" else None,
        )

    def cancel(self, remote_job_id: str) -> None:
        self.cancelled.append(remote_job_id)


class _PassThroughValidator:
    def validate(self, payload: dict[str, object]) -> int:
        return int(payload.get("seed") or 1)

    def execute(self, job: JobRecord, **_kwargs: object) -> JobResult:
        raise AssertionError("local execute should not run")


def _job_result() -> JobResult:
    return JobResult(
        generation_id="11111111-1111-1111-1111-111111111111",
        status="completed",
        operation="text_to_image",
        asset_type="texture",
        seed=7,
        width=8,
        height=8,
        elapsed_seconds=0.1,
        resources={"image": "/image", "manifest": "/manifest"},
        schema_versions={"generation_manifest": "1.5"},
    )


def test_network_production_requires_authentication() -> None:
    with pytest.raises(ValidationError, match="AUTHENTICATION_MODE"):
        Settings(environment="production", bind_host="0.0.0.0")


def test_api_key_mode_requires_a_key() -> None:
    with pytest.raises(ValidationError, match="API_KEY"):
        Settings(authentication_mode="api_key")


def test_remote_worker_mode_requires_a_url() -> None:
    with pytest.raises(ValidationError, match="REMOTE_WORKER_URL"):
        Settings(worker_mode="remote")


def test_api_authentication_and_rate_limit(settings: Settings) -> None:
    settings.authentication_mode = "api_key"
    settings.api_key = "test-secret"
    settings.max_requests_per_minute = 1

    app = create_app(settings=settings, backend=FakeImageGenerationBackend(device_name="cpu"))
    with TestClient(app) as protected:
        assert protected.get("/health").status_code == 200
        assert protected.get("/ready").status_code == 200
        assert protected.get("/api/v1/capabilities").status_code == 401
        headers = {"Authorization": "Bearer test-secret"}
        assert protected.get("/api/v1/capabilities", headers=headers).status_code == 200
        response = protected.get("/api/v1/capabilities", headers=headers)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_ready_reports_storage_and_runtime(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["storage"]["jobs"] is True
    assert payload["storage"]["models"] is True
    assert payload["runtime"]["selected_device"] == "cpu"


def test_health_does_not_load_weights(
    client: TestClient, fake_backend: FakeImageGenerationBackend
) -> None:
    before = fake_backend.capability_calls
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is False
    assert fake_backend.capability_calls == before


def test_runtime_validator_reports_unavailable_cuda_as_fatal_when_selected() -> None:
    settings = Settings(device="cuda")
    probe = _Probe(HardwareSnapshot(cuda_available=False, accelerate_present=True))
    with patch(
        "unity_ai_assets.inference.model_manager.torch.cuda.is_available",
        return_value=False,
    ):
        report = RuntimeValidator(settings, probe=probe).validate()
    assert not report.usable
    assert any(
        check.name == "device_selection" and check.status == "fatal" for check in report.checks
    )


def test_runtime_validator_marks_low_vram_as_insufficient_for_active_model() -> None:
    class _Active:
        id = "local/sdxl"
        family = "sdxl"
        is_usable = True
        compatibility = type(
            "Compat",
            (),
            {
                "is_supported_schema": True,
                "schema_status": "supported",
                "model_family": "sdxl",
                "pipeline_class": "StableDiffusionXLPipeline",
                "supported_operations": ("text_to_image",),
            },
        )()

    class _Models:
        def get_active(self) -> _Active:
            return _Active()

    settings = Settings(device="cuda")
    probe = _Probe(
        HardwareSnapshot(
            cuda_available=True,
            total_vram_bytes=2 * 1024 * 1024 * 1024,
            accelerate_present=True,
            device_name="Test GPU",
        )
    )
    with patch(
        "unity_ai_assets.inference.model_manager.torch.cuda.is_available",
        return_value=True,
    ):
        report = RuntimeValidator(settings, probe=probe, model_service=_Models()).validate()
    assert report.usable
    assert any(check.status == "insufficient_resources" for check in report.checks)


def test_remote_executor_completes_and_is_idempotent() -> None:
    result = _job_result()
    client = _FakeRemoteClient(result)
    executor = RemoteGenerationExecutor(_PassThroughValidator(), client, poll_interval=0)
    now = utc_now_iso()
    job = JobRecord(
        job_id="22222222-2222-2222-2222-222222222222",
        state=JobState.QUEUED,
        generation_type="text_to_image",
        asset_type="texture",
        request={"prompt": "metal", "seed": 7},
        created_at=now,
        updated_at=now,
    )
    completed = executor.execute(job, cancel_event=threading.Event(), on_progress=lambda _p: None)
    assert completed.generation_id == result.generation_id
    assert len(client.submitted) == 1


def test_remote_executor_cancels() -> None:
    result = _job_result()
    client = _FakeRemoteClient(result, states=["running", "cancelled"])
    executor = RemoteGenerationExecutor(_PassThroughValidator(), client, poll_interval=0)
    now = utc_now_iso()
    job = JobRecord(
        job_id="33333333-3333-3333-3333-333333333333",
        state=JobState.RUNNING,
        generation_type="text_to_image",
        asset_type="texture",
        request={"prompt": "metal", "seed": 7},
        created_at=now,
        updated_at=now,
    )
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(GenerationCancelledError):
        executor.execute(job, cancel_event=cancel, on_progress=lambda _p: None)
    assert client.cancelled == [job.job_id]


def test_http_remote_worker_parses_status(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "job_id": "abc",
                    "state": "completed",
                    "result": _job_result().to_dict(),
                }
            ).encode("utf-8")

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(request: object, timeout: float = 0) -> _Response:
        captured["url"] = getattr(request, "full_url", None)
        return _Response()

    monkeypatch.setattr(
        "unity_ai_assets.services.remote_worker_http.urllib.request.urlopen",
        fake_urlopen,
    )
    status = HttpRemoteWorkerClient("http://worker.example/").get_status("abc")
    assert status.state == "completed"
    assert status.result is not None
    assert status.result.generation_id == _job_result().generation_id


def test_job_store_survives_reopen(tmp_path: Path) -> None:
    directory = tmp_path / "jobs"
    store = JobStore(directory)
    now = utc_now_iso()
    record = JobRecord(
        job_id="44444444-4444-4444-4444-444444444444",
        state=JobState.QUEUED,
        generation_type="text_to_image",
        asset_type="texture",
        request={"prompt": "stone"},
        created_at=now,
        updated_at=now,
    )
    store.save(record)
    restored = JobStore(directory)
    loaded = restored.get(record.job_id)
    assert loaded.request["prompt"] == "stone"
    assert loaded.state is JobState.QUEUED
