"""HTTP tests for batch orchestration endpoints."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from unity_ai_assets.core.config import Settings
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    output = tmp_path / "generated"
    output.mkdir(exist_ok=True)
    values: dict[str, object] = {
        "model_id": "fake/test-model",
        "model_family": "sd15",
        "device": "cpu",
        "output_directory": output,
        "max_width": 1024,
        "max_height": 1024,
        "job_auto_retry": False,
        "max_job_retries": 2,
        "max_batch_jobs": 16,
        "log_level": "WARNING",
        "app_version": "0.10.0-test",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "prompts": ["rusted metal", "mossy brick"],
        "variation_count": 2,
        "seed_mode": "fixed",
        "seed": 11,
        "request": {
            "prompt": "placeholder",
            "width": 32,
            "height": 32,
            "steps": 2,
            "seed": 1,
            "output_name": "batch",
            "asset_type": "texture",
            "operation": "text_to_image",
        },
    }
    payload.update(overrides)
    return payload


def _wait_batch(client: TestClient, batch_id: str, timeout: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    body: dict[str, object] = {}
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/batches/{batch_id}").json()
        if body["state"] in {"completed", "partial_success", "failed", "cancelled"}:
            return body
        time.sleep(0.02)
    return body


def test_batch_preview_submit_status_and_job_filter(tmp_path: Path) -> None:
    app = create_app(
        settings=_settings(tmp_path),
        backend=FakeImageGenerationBackend(delay_seconds=0.02),
    )
    with TestClient(app) as client:
        preview = client.post("/api/v1/batches/preview", json=_body())
        assert preview.status_code == 200
        preview_body = preview.json()
        assert preview_body["job_count"] == 4
        assert preview_body["seed_summary"]
        assert preview_body["items"][0]["seed"] == 11
        assert "content_base64" not in preview.text

        submitted = client.post("/api/v1/batches", json=_body())
        assert submitted.status_code == 202
        batch = submitted.json()
        batch_id = batch["batch_id"]
        assert len(batch["job_ids"]) == 4
        assert batch["counts"]["total"] == 4
        assert all(job["batch_id"] == batch_id for job in batch["jobs"])
        assert batch["jobs"][0]["prompt_index"] == 0
        assert batch["jobs"][1]["variation_index"] == 1

        finished = _wait_batch(client, batch_id)
        assert finished["state"] == "completed"
        assert finished["progress"]["completed_jobs"] == 4
        assert finished["progress"]["finished_jobs"] == 4
        assert finished["counts"]["failed"] == 0

        filtered = client.get("/api/v1/jobs", params={"batch_id": batch_id, "limit": 20})
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 4
        history = client.get("/api/v1/batches")
        assert history.status_code == 200
        assert history.json()["total"] >= 1
        assert history.json()["batches"][0]["batch_id"] == batch_id


def test_batch_partial_failure_cancel_and_retry(tmp_path: Path) -> None:
    backend = FakeImageGenerationBackend(
        delay_seconds=0.02,
        fail_if=lambda request: "fail" in request.prompt,
    )
    app = create_app(settings=_settings(tmp_path, max_job_retries=2), backend=backend)
    with TestClient(app) as client:
        submitted = client.post(
            "/api/v1/batches",
            json=_body(prompts=["ok rust", "fail rust"], variation_count=1),
        )
        batch_id = submitted.json()["batch_id"]
        finished = _wait_batch(client, batch_id)
        assert finished["state"] == "partial_success"
        assert finished["counts"]["completed"] == 1
        assert finished["counts"]["failed"] == 1
        failed = next(job for job in finished["jobs"] if job["state"] == "failed")
        assert failed["error"]["code"] == "INFERENCE_FAILED"
        succeeded = next(job for job in finished["jobs"] if job["state"] == "completed")
        assert succeeded["result"]["generation_id"]

        backend._fail_if = None
        retried = client.post(f"/api/v1/batches/{batch_id}/retry-failed")
        assert retried.status_code == 202
        recovered = _wait_batch(client, batch_id)
        assert recovered["state"] == "completed"
        assert recovered["counts"]["completed"] == 2


def test_batch_cancel_and_invalid_payloads(tmp_path: Path) -> None:
    app = create_app(
        settings=_settings(tmp_path, max_batch_jobs=3),
        backend=FakeImageGenerationBackend(delay_seconds=0.4),
    )
    with TestClient(app) as client:
        too_large = client.post(
            "/api/v1/batches",
            json=_body(prompts=["a", "b"], variation_count=2, seed_mode="fixed", seed=1),
        )
        assert too_large.status_code == 422
        assert too_large.json()["error"]["code"] == "BATCH_TOO_LARGE"

        empty = client.post("/api/v1/batches", json=_body(prompts=["  "], variation_count=1))
        assert empty.status_code == 422

        first = client.post(
            "/api/v1/batches",
            json=_body(prompts=["slow"], variation_count=1, seed_mode="fixed", seed=2),
        )
        second = client.post(
            "/api/v1/batches",
            json=_body(prompts=["queued"], variation_count=1, seed_mode="fixed", seed=3),
        )
        batch_id = second.json()["batch_id"]
        cancelled = client.post(f"/api/v1/batches/{batch_id}/cancel")
        assert cancelled.status_code == 200
        body = cancelled.json()
        assert body["counts"]["cancelled"] + body["counts"]["cancelling"] >= 1
        missing = client.get("/api/v1/batches/99999999-9999-9999-9999-999999999999")
        assert missing.status_code == 404
        assert first.status_code == 202
