"""Integration tests for HTTP API using the fake backend."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from unity_ai_assets.core.config import Settings
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_loaded"] is True
    assert payload["device"] == "cpu"


def test_valid_generation_request(client: TestClient, output_dir: Path) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "low-resolution rusted industrial wall texture, PS1 game aesthetic",
            "negative_prompt": "text, logo, watermark, photorealistic scene",
            "width": 64,
            "height": 64,
            "steps": 5,
            "guidance_scale": 7.0,
            "seed": 12345,
            "output_name": "rusted_wall",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["seed"] == 12345
    assert payload["width"] == 64
    assert payload["height"] == 64
    assert payload["generation_id"]
    assert payload["elapsed_seconds"] >= 0
    image_path = Path(payload["image_path"])
    metadata_path = Path(payload["metadata_path"])
    assert image_path.is_file()
    assert metadata_path.is_file()
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert meta["seed"] == 12345
    assert meta["prompt"].startswith("low-resolution")


def test_invalid_dimensions(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "wall", "width": 500, "height": 512},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_parameters"
    assert "divisible by 8" in body["message"]


def test_excessive_dimensions(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "wall", "width": 2048, "height": 512},
    )
    assert response.status_code == 422
    assert "MAX_WIDTH" in response.json()["message"]


def test_missing_prompt(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"width": 64, "height": 64},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_parameters"


def test_random_seed_assignment(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "floor", "width": 32, "height": 32, "steps": 1},
    )
    assert response.status_code == 200
    seed = response.json()["seed"]
    assert isinstance(seed, int)


def test_explicit_seed_preservation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "floor", "width": 32, "height": 32, "steps": 1, "seed": 99},
    )
    assert response.status_code == 200
    assert response.json()["seed"] == 99


def test_output_name_sanitization_rejection(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "wall",
            "width": 32,
            "height": 32,
            "output_name": "../evil",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_parameters"


def test_backend_failure_translated_to_api(tmp_path: Path) -> None:
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        output_directory=tmp_path / "generated",
        max_width=1024,
        max_height=1024,
        log_level="WARNING",
    )
    (tmp_path / "generated").mkdir()
    app = create_app(settings=settings, backend=FakeImageGenerationBackend(fail=True))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/generations/textures",
            json={"prompt": "wall", "width": 32, "height": 32, "steps": 1},
        )
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "inference_failed"
    assert "stack" not in body
    assert "Traceback" not in body["message"]


def test_inference_backend_substitution(tmp_path: Path) -> None:
    settings = Settings(
        model_id="other/model",
        device="cpu",
        output_directory=tmp_path / "generated",
        log_level="WARNING",
    )
    (tmp_path / "generated").mkdir()
    backend = FakeImageGenerationBackend(model_id="injected/fake")
    app = create_app(settings=settings, backend=backend)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/generations/textures",
            json={
                "prompt": "injected",
                "width": 32,
                "height": 32,
                "steps": 1,
                "seed": 1,
                "output_name": "injected_tex",
            },
        )
    assert response.status_code == 200
    meta = json.loads(Path(response.json()["metadata_path"]).read_text(encoding="utf-8"))
    assert meta["model_id"] == "injected/fake"
    assert len(backend.calls) == 1
