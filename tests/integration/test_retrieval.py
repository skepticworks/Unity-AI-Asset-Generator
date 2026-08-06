"""Tests for safe generation artifact retrieval endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.version import GENERATION_MANIFEST_SCHEMA_VERSION
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app


def _make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        output_directory=tmp_path / "generated",
        max_width=1024,
        max_height=1024,
        log_level="WARNING",
    )
    (tmp_path / "generated").mkdir(exist_ok=True)
    app = create_app(settings=settings, backend=FakeImageGenerationBackend())
    return TestClient(app)


def test_retrieve_existing_image_and_manifest(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        create = client.post(
            "/api/v1/generations/textures",
            json={
                "prompt": "wall",
                "width": 32,
                "height": 32,
                "steps": 1,
                "seed": 7,
                "output_name": "wall_tex",
            },
        )
        assert create.status_code == 200
        body = create.json()
        generation_id = body["generation_id"]
        assert body["resources"]["image"] == f"/api/v1/generations/{generation_id}/image"
        assert body["resources"]["manifest"] == f"/api/v1/generations/{generation_id}/manifest"

        image = client.get(body["resources"]["image"])
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/png")
        assert image.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(image.content) > 0

        manifest = client.get(body["resources"]["manifest"])
        assert manifest.status_code == 200
        assert manifest.headers["content-type"].startswith("application/json")
        payload = manifest.json()
        assert payload["schema"]["version"] == GENERATION_MANIFEST_SCHEMA_VERSION
        assert payload["generation"]["id"] == generation_id
        assert payload["request"]["seed"] == 7
        assert payload["request"]["prompt"] == "wall"
        assert payload["outputs"][0]["sha256"]
        assert payload["outputs"][0]["byte_size"] == len(image.content)
        assert payload["outputs"][0]["relative_path"] == "wall_tex.png"
        # Relative path only — no absolute filesystem paths in manifest.
        assert not payload["outputs"][0]["relative_path"].startswith("/")
        assert ":" not in payload["outputs"][0]["relative_path"]

        # Deprecated metadata alias returns the same manifest document.
        legacy = client.get(f"/api/v1/generations/{generation_id}/metadata")
        assert legacy.status_code == 200
        assert legacy.json()["schema"]["version"] == GENERATION_MANIFEST_SCHEMA_VERSION


def test_image_hash_matches_manifest(tmp_path: Path) -> None:
    import hashlib

    with _make_client(tmp_path) as client:
        create = client.post(
            "/api/v1/generations/textures",
            json={"prompt": "hash", "width": 32, "height": 32, "steps": 1, "seed": 1},
        )
        generation_id = create.json()["generation_id"]
        image = client.get(f"/api/v1/generations/{generation_id}/image")
        manifest = client.get(f"/api/v1/generations/{generation_id}/manifest").json()
        digest = hashlib.sha256(image.content).hexdigest()
        assert digest == manifest["outputs"][0]["sha256"]
        assert len(image.content) == manifest["outputs"][0]["byte_size"]


def test_unknown_generation_id(tmp_path: Path) -> None:
    unknown = "11111111-1111-1111-1111-111111111111"
    with _make_client(tmp_path) as client:
        response = client.get(f"/api/v1/generations/{unknown}/image")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "GENERATION_NOT_FOUND"


def test_invalid_generation_id(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.get("/api/v1/generations/not-a-uuid/image")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "GENERATION_REQUEST_INVALID"


def test_path_traversal_generation_id_rejected(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        for bad_id in ("../etc/passwd", "..\\secret", "aaaa/bbbb"):
            response = client.get(f"/api/v1/generations/{bad_id}/image")
            assert response.status_code in {404, 422}
            assert response.headers.get("content-type", "").startswith("application/json")


def test_cannot_access_files_outside_generation_directory(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\n" + b"not-served")
    with _make_client(tmp_path) as client:
        response = client.get("/api/v1/generations/secret.png/image")
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "GENERATION_REQUEST_INVALID"
        assert outside.read_bytes().startswith(b"\x89PNG")


def test_legacy_metadata_compatibility(tmp_path: Path) -> None:
    """Existing flat metadata remains readable via the manifest endpoint."""
    generated = tmp_path / "generated"
    generation_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    directory = generated / generation_id
    directory.mkdir(parents=True)
    (directory / "legacy.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"legacy")
    legacy = {
        "generation_id": generation_id,
        "created_at_utc": "2026-08-05T18:26:35.172855Z",
        "model_id": "runwayml/stable-diffusion-v1-5",
        "model_revision": None,
        "prompt": "legacy wall",
        "negative_prompt": "photo",
        "seed": 42,
        "width": 64,
        "height": 64,
        "steps": 10,
        "guidance_scale": 7.0,
        "device": "cuda",
        "torch_dtype": "float16",
        "app_version": "0.2.0",
        "elapsed_seconds": 1.5,
        "output_filename": "legacy.png",
    }
    (directory / "legacy.json").write_text(json.dumps(legacy), encoding="utf-8")

    with _make_client(tmp_path) as client:
        response = client.get(f"/api/v1/generations/{generation_id}/manifest")
        assert response.status_code == 200
        payload = response.json()
        assert payload["generation"]["id"] == generation_id
        assert payload["request"]["prompt"] == "legacy wall"
        assert payload["model"]["family"] == "unknown"
        assert payload["runtime"]["scheduler"] == "unknown"


def test_unsupported_manifest_version(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generation_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    directory = generated / generation_id
    directory.mkdir(parents=True)
    (directory / "tex.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x")
    bad = {
        "schema": {"name": "generation-manifest", "version": "99.0"},
        "generation": {},
    }
    (directory / "manifest.json").write_text(json.dumps(bad), encoding="utf-8")
    with _make_client(tmp_path) as client:
        response = client.get(f"/api/v1/generations/{generation_id}/manifest")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MANIFEST_SCHEMA_UNSUPPORTED"


def test_missing_manifest(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generation_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    directory = generated / generation_id
    directory.mkdir(parents=True)
    (directory / "tex.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x")
    with _make_client(tmp_path) as client:
        response = client.get(f"/api/v1/generations/{generation_id}/manifest")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MANIFEST_NOT_FOUND"
