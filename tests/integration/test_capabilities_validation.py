"""Additional integration tests for capability and validation contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend


def test_prompt_too_long(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "x" * 2001, "width": 32, "height": 32, "steps": 1},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "GENERATION_REQUEST_INVALID"
    assert error["details"]["fields"]["prompt"][0]["code"] == "VALUE_TOO_LONG"


def test_invalid_guidance(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "wall",
            "width": 32,
            "height": 32,
            "steps": 1,
            "guidance_scale": 999.0,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"]["guidance_scale"][0]["code"] == (
        "VALUE_ABOVE_MAXIMUM"
    )


def test_excessive_steps(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "wall", "width": 32, "height": 32, "steps": 999},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"]["steps"][0]["code"] == (
        "VALUE_ABOVE_MAXIMUM"
    )


def test_invalid_seed(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "wall", "width": 32, "height": 32, "steps": 1, "seed": -1},
    )
    assert response.status_code == 422
    # May be REQUEST_BODY_INVALID from pydantic or GENERATION_REQUEST_INVALID from policy.
    assert response.json()["error"]["code"] in {
        "REQUEST_BODY_INVALID",
        "GENERATION_REQUEST_INVALID",
    }


def test_output_name_too_long(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "wall",
            "width": 32,
            "height": 32,
            "steps": 1,
            "output_name": "a" * 101,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GENERATION_REQUEST_INVALID"


def test_malformed_body_translation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        content="{not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "REQUEST_BODY_INVALID"
    assert "request_id" in body["error"]


def test_request_id_in_errors(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "wall", "width": 500, "height": 512},
        headers={"X-Request-ID": "err-check-1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["request_id"] == "err-check-1"
    assert response.headers["X-Request-ID"] == "err-check-1"


def test_capabilities_do_not_load_model(
    client: TestClient,
    fake_backend: FakeImageGenerationBackend,
) -> None:
    assert fake_backend.model_loaded is False
    client.get("/api/v1/capabilities")
    assert fake_backend.model_loaded is False
    assert fake_backend.calls == []
