"""Integration tests for HTTP API using the fake backend."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.version import (
    API_MAJOR_VERSION,
    APPLICATION_NAME,
    CAPABILITIES_SCHEMA_VERSION,
    GENERATION_MANIFEST_SCHEMA_VERSION,
)
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_loaded"] is False
    assert payload["resolved_device"] == "cpu"
    assert payload["application_version"] == "0.3.0-test"
    assert "X-Request-ID" in response.headers


def test_service_root_endpoint(client: TestClient) -> None:
    """GET / returns service identity so IDE/browser probes are not misleading 404s."""
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "unity-ai-assets"
    assert payload["status"] == "ok"
    assert payload["endpoints"]["health"] == "/health"
    assert payload["endpoints"]["capabilities"] == "/api/v1/capabilities"
    assert payload["endpoints"]["jobs"] == "/api/v1/jobs"
    assert payload["endpoints"]["batches"] == "/api/v1/batches"
    assert payload["endpoints"]["models"] == "/api/v1/models"
    # CDP discovery probes must not be faked as Chrome DevTools.
    cdp = client.get("/json/version")
    assert cdp.status_code == 404


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
    assert payload["operation"] == "text_to_image"
    assert payload["asset_type"] == "texture"
    assert payload["seed"] == 12345
    assert payload["width"] == 64
    assert payload["height"] == 64
    assert payload["generation_id"]
    assert payload["elapsed_seconds"] >= 0
    assert payload["resources"]["image"] == (
        f"/api/v1/generations/{payload['generation_id']}/image"
    )
    assert payload["resources"]["manifest"] == (
        f"/api/v1/generations/{payload['generation_id']}/manifest"
    )
    assert payload["schema_versions"]["generation_manifest"] == GENERATION_MANIFEST_SCHEMA_VERSION
    # Deprecated fields may still be present for local debugging.
    assert "image_path" in payload
    image_path = Path(payload["image_path"])
    metadata_path = Path(payload["metadata_path"])
    assert image_path.is_file()
    assert metadata_path.is_file()
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert meta["schema"]["version"] == GENERATION_MANIFEST_SCHEMA_VERSION
    assert meta["request"]["seed"] == 12345
    assert meta["request"]["prompt"].startswith("low-resolution")
    assert meta["outputs"][0]["sha256"]
    assert meta["outputs"][0]["byte_size"] > 0
    # No absolute Windows drive paths in public resources.
    assert not payload["resources"]["image"].startswith("C:")
    assert "\\" not in payload["resources"]["manifest"]


def test_invalid_dimensions(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "wall", "width": 500, "height": 512},
    )
    assert response.status_code == 422
    body = response.json()
    error = body["error"]
    assert error["code"] == "GENERATION_REQUEST_INVALID"
    assert "request_id" in error
    assert "width" in error["details"]["fields"]
    assert error["details"]["fields"]["width"][0]["code"] == "VALUE_NOT_MULTIPLE"


def test_excessive_dimensions(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"prompt": "wall", "width": 2048, "height": 512},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "GENERATION_REQUEST_INVALID"
    assert error["details"]["fields"]["width"][0]["code"] == "VALUE_ABOVE_MAXIMUM"


def test_missing_prompt(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={"width": 64, "height": 64},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "REQUEST_BODY_INVALID"


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
    assert response.json()["error"]["code"] == "GENERATION_REQUEST_INVALID"


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
    assert body["error"]["code"] == "INFERENCE_FAILED"
    assert "stack" not in body
    assert "Traceback" not in body["error"]["message"]


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
    generation_id = response.json()["generation_id"]
    with TestClient(app) as client:
        manifest = client.get(f"/api/v1/generations/{generation_id}/manifest").json()
    assert manifest["model"]["id"] == "injected/fake"
    assert len(backend.calls) == 1


def test_capabilities_endpoint(
    client: TestClient, fake_backend: FakeImageGenerationBackend
) -> None:
    before = fake_backend.capability_calls
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    payload = response.json()
    assert payload["api"]["major"] == API_MAJOR_VERSION
    assert payload["schemas"]["capabilities"] == CAPABILITIES_SCHEMA_VERSION
    assert payload["schemas"]["generation_manifest"] == GENERATION_MANIFEST_SCHEMA_VERSION
    assert payload["application"]["name"] == APPLICATION_NAME
    assert payload["application"]["version"] == "0.3.0-test"
    assert payload["model"]["id"] == "fake/test-model"
    assert payload["model"]["family"] == "sd15"
    assert payload["runtime"]["model_loaded"] is False
    assert payload["runtime"]["configured_device"] == "cpu"
    assert payload["runtime"]["resolved_device"] == "cpu"
    assert payload["operations"]["text_to_image"]["supported"] is True
    assert payload["operations"]["image_to_image"]["supported"] is True
    assert payload["operations"]["image_to_image"]["denoising_strength"]["default"] == 0.75
    assert "png" in payload["operations"]["image_to_image"]["source_image"]["supported_formats"]
    assert payload["operations"]["inpainting"]["supported"] is True
    assert payload["operations"]["inpainting"]["mask_image"]["convention"] == "white_inpaints"
    assert payload["api"]["minor"] == 5
    assert payload["batches"]["supported"] is True
    assert payload["model_management"]["supported"] is True
    assert payload["model_management"]["offline_mode"] is False
    assert payload["operations"]["text_to_image"]["dimensions"]["maximum_width"] == 1024
    assert payload["operations"]["text_to_image"]["schedulers"]["selection_supported"] is False
    assert payload["precision"]["user_selectable"] is False
    assert fake_backend.calls == []
    assert fake_backend.capability_calls == before + 1
    assert fake_backend.model_loaded is False


def test_request_id_propagation(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "client-req-001"})
    assert response.headers["X-Request-ID"] == "client-req-001"


def test_invalid_request_id_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert response.headers["X-Request-ID"] != "bad id with spaces"
    assert response.headers["X-Request-ID"]


def _png_base64(width: int = 64, height: int = 64) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(180, 40, 20)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_img2img_generation_request(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "weathered variation of the source plate",
            "width": 64,
            "height": 64,
            "steps": 5,
            "seed": 42,
            "output_name": "img2img_wall",
            "operation": "image_to_image",
            "denoising_strength": 0.35,
            "source_image": {
                "content_base64": _png_base64(),
                "media_type": "image/png",
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["operation"] == "image_to_image"
    assert payload["seed"] == 42
    manifest = client.get(payload["resources"]["manifest"]).json()
    assert manifest["generation"]["operation"] == "image_to_image"
    assert manifest["request"]["denoising_strength"] == 0.35
    assert manifest["request"]["source_image"]["format"] == "png"
    assert manifest["request"]["source_image"]["width"] == 64
    assert manifest["request"]["source_image"]["sha256"]


def test_img2img_missing_source_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "missing source",
            "width": 64,
            "height": 64,
            "operation": "image_to_image",
            "output_name": "missing",
        },
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] in {"REQUEST_BODY_INVALID", "GENERATION_REQUEST_INVALID"}


def _mask_base64(width: int = 64, height: int = 64) -> str:
    mask = Image.new("L", (width, height), color=0)
    for x in range(width // 2):
        for y in range(height):
            mask.putpixel((x, y), 255)
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_inpainting_generation_request(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "replace the damaged region",
            "width": 64,
            "height": 64,
            "steps": 5,
            "seed": 42,
            "output_name": "inpaint_wall",
            "operation": "inpainting",
            "denoising_strength": 0.35,
            "source_image": {
                "content_base64": _png_base64(),
                "media_type": "image/png",
            },
            "mask_image": {
                "content_base64": _mask_base64(),
                "media_type": "image/png",
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["operation"] == "inpainting"
    assert payload["seed"] == 42
    manifest = client.get(payload["resources"]["manifest"]).json()
    assert manifest["generation"]["operation"] == "inpainting"
    assert manifest["request"]["denoising_strength"] == 0.35
    assert manifest["request"]["mask_convention"] == "white_inpaints"
    assert manifest["request"]["source_image"]["format"] == "png"
    assert manifest["request"]["mask_image"]["format"] == "png"
    assert manifest["request"]["mask_image"]["width"] == 64
    assert manifest["request"]["mask_image"]["sha256"]


def test_inpainting_missing_mask_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "missing mask",
            "width": 64,
            "height": 64,
            "operation": "inpainting",
            "source_image": {
                "content_base64": _png_base64(),
                "media_type": "image/png",
            },
            "output_name": "missing",
        },
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] in {"REQUEST_BODY_INVALID", "GENERATION_REQUEST_INVALID"}


def test_img2img_with_mask_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "should not accept mask",
            "width": 64,
            "height": 64,
            "operation": "image_to_image",
            "source_image": {
                "content_base64": _png_base64(),
                "media_type": "image/png",
            },
            "mask_image": {
                "content_base64": _mask_base64(),
                "media_type": "image/png",
            },
            "output_name": "nope",
        },
    )
    assert response.status_code == 422


def test_txt2img_with_source_image_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "should not accept source",
            "width": 64,
            "height": 64,
            "operation": "text_to_image",
            "source_image": {
                "content_base64": _png_base64(),
                "media_type": "image/png",
            },
            "output_name": "nope",
        },
    )
    assert response.status_code == 422
