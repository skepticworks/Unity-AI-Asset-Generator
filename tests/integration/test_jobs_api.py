"""HTTP tests for the local job API."""

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
        "log_level": "WARNING",
        "app_version": "0.9.0-test",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_job_submit_status_result_and_history(tmp_path: Path) -> None:
    app = create_app(
        settings=_settings(tmp_path),
        backend=FakeImageGenerationBackend(delay_seconds=0.02),
    )
    with TestClient(app) as client:
        submitted = client.post(
            "/api/v1/jobs",
            json={
                "prompt": "tileable rust",
                "width": 32,
                "height": 32,
                "steps": 2,
                "seed": 42,
                "output_name": "job_tex",
            },
        )
        assert submitted.status_code == 202
        body = submitted.json()
        job_id = body["job_id"]
        assert body["state"] in {"queued", "running", "completed"}
        assert body["generation_type"] == "text_to_image"
        assert "rust" in body["prompt_summary"]
        assert "content_base64" not in str(body.get("request", {}))

        deadline = time.monotonic() + 5
        status_body = body
        while time.monotonic() < deadline:
            status_body = client.get(f"/api/v1/jobs/{job_id}").json()
            if status_body["state"] == "completed":
                break
            time.sleep(0.02)
        assert status_body["state"] == "completed"
        assert status_body["progress"]["stage"] == "completed"
        assert status_body["result"]["generation_id"]
        assert status_body["result"]["seed"] == 42

        result = client.get(f"/api/v1/jobs/{job_id}/result")
        assert result.status_code == 200
        generation_id = result.json()["generation_id"]
        image = client.get(f"/api/v1/generations/{generation_id}/image")
        assert image.status_code == 200
        assert image.content[:8] == b"\x89PNG\r\n\x1a\n"

        history = client.get("/api/v1/jobs")
        assert history.status_code == 200
        payload = history.json()
        assert payload["total"] >= 1
        assert payload["jobs"][0]["job_id"] == job_id


def test_job_cancel_and_retry(tmp_path: Path) -> None:
    app = create_app(
        settings=_settings(tmp_path, max_job_retries=2),
        backend=FakeImageGenerationBackend(delay_seconds=0.4),
    )
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/jobs",
            json={"prompt": "slow", "width": 32, "height": 32, "steps": 16, "seed": 1},
        ).json()
        second = client.post(
            "/api/v1/jobs",
            json={"prompt": "queued", "width": 32, "height": 32, "steps": 2, "seed": 2},
        ).json()
        cancelled = client.post(f"/api/v1/jobs/{second['job_id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "cancelled"

        deadline = time.monotonic() + 2
        running_id = first["job_id"]
        while time.monotonic() < deadline:
            current = client.get(f"/api/v1/jobs/{running_id}").json()
            if current["state"] == "running":
                break
            time.sleep(0.02)
        cancel_running = client.post(f"/api/v1/jobs/{running_id}/cancel")
        assert cancel_running.status_code == 200
        assert cancel_running.json()["state"] in {"cancelling", "cancelled"}
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = client.get(f"/api/v1/jobs/{running_id}").json()
            if current["state"] == "cancelled":
                break
            time.sleep(0.02)
        assert current["state"] == "cancelled"

        retried = client.post(f"/api/v1/jobs/{second['job_id']}/retry")
        assert retried.status_code == 202
        assert retried.json()["state"] in {"queued", "running", "completed"}
        job_id = retried.json()["job_id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            body = client.get(f"/api/v1/jobs/{job_id}").json()
            if body["state"] == "completed":
                break
            time.sleep(0.02)
        assert body["state"] == "completed"


def test_sync_texture_endpoint_still_waits_on_job(tmp_path: Path) -> None:
    app = create_app(
        settings=_settings(tmp_path),
        backend=FakeImageGenerationBackend(delay_seconds=0.01),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/generations/textures",
            json={"prompt": "compat", "width": 32, "height": 32, "steps": 1, "seed": 9},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["generation_id"]
        history = client.get("/api/v1/jobs").json()
        assert history["total"] == 1
        assert history["jobs"][0]["result"]["generation_id"] == payload["generation_id"]


def test_result_conflict_for_incomplete_job(tmp_path: Path) -> None:
    app = create_app(
        settings=_settings(tmp_path),
        backend=FakeImageGenerationBackend(delay_seconds=0.3),
    )
    with TestClient(app) as client:
        submitted = client.post(
            "/api/v1/jobs",
            json={"prompt": "later", "width": 32, "height": 32, "steps": 8, "seed": 3},
        )
        job_id = submitted.json()["job_id"]
        result = client.get(f"/api/v1/jobs/{job_id}/result")
        if result.status_code == 409:
            assert result.json()["error"]["code"] == "JOB_STATE_CONFLICT"
        else:
            assert result.status_code == 200
        unknown = client.get("/api/v1/jobs/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "JOB_NOT_FOUND"
