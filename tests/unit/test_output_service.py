"""Unit tests for output name sanitization and persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from unity_ai_assets.core.errors import GenerationRequestInvalidError, OutputPersistenceError
from unity_ai_assets.core.version import GENERATION_MANIFEST_SCHEMA_VERSION
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest
from unity_ai_assets.services.output_service import OutputService, sanitize_output_name, sha256_file


@pytest.mark.parametrize(
    "raw",
    [
        "../escape",
        "..\\escape",
        "foo/bar",
        "foo\\bar",
        "",
        " ",
        "bad name",
        "has.dot",
        "-leading",
        "a" * 101,
    ],
)
def test_sanitize_output_name_rejects_unsafe_values(raw: str) -> None:
    with pytest.raises(GenerationRequestInvalidError):
        sanitize_output_name(raw, max_length=100)


@pytest.mark.parametrize("raw", ["rusted_wall", "Wall01", "a", "item-icon_2", "a" * 100])
def test_sanitize_output_name_accepts_safe_values(raw: str) -> None:
    assert sanitize_output_name(raw, max_length=100) == raw


def test_manifest_creation_with_hash(tmp_path: Path) -> None:
    service = OutputService(tmp_path / "generated", app_version="0.3.0", model_family="sd15")
    (tmp_path / "generated").mkdir()
    request = GenerationRequest(
        prompt="rusty wall",
        negative_prompt="photo",
        width=64,
        height=64,
        steps=10,
        guidance_scale=7.0,
        seed=42,
        output_name="rusted_wall",
        generation_id="11111111-1111-1111-1111-111111111111",
    )
    generated = GeneratedImage(
        image=Image.new("RGB", (64, 64), color=(10, 20, 30)),
        seed=42,
        width=64,
        height=64,
        elapsed_seconds=1.25,
        device="cpu",
        torch_dtype="float32",
        model_id="fake/model",
        model_revision="abc",
    )

    result = service.persist(request, generated)
    meta_path = Path(result.metadata_path)
    assert meta_path.is_file()
    assert meta_path.name == "manifest.json"
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert payload["schema"]["version"] == GENERATION_MANIFEST_SCHEMA_VERSION
    assert payload["generation"]["id"] == request.generation_id
    assert payload["request"]["prompt"] == "rusty wall"
    assert payload["request"]["seed"] == 42
    assert payload["model"]["id"] == "fake/model"
    assert payload["model"]["family"] == "sd15"
    assert payload["outputs"][0]["relative_path"] == "rusted_wall.png"
    assert payload["outputs"][0]["sha256"] == result.image_sha256
    assert payload["outputs"][0]["byte_size"] == result.image_byte_size
    assert result.image_sha256 == sha256_file(Path(result.image_path))
    assert Path(result.image_path).stat().st_size == result.image_byte_size
    assert Path(result.image_path).is_file()


def test_never_overwrites_existing_generation_directory(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    generation_id = "22222222-2222-2222-2222-222222222222"
    (root / generation_id).mkdir()
    service = OutputService(root, app_version="0.3.0")
    request = GenerationRequest(
        prompt="x",
        negative_prompt="",
        width=32,
        height=32,
        steps=1,
        guidance_scale=1.0,
        seed=1,
        output_name="texture",
        generation_id=generation_id,
    )
    generated = GeneratedImage(
        image=Image.new("RGB", (32, 32)),
        seed=1,
        width=32,
        height=32,
        elapsed_seconds=0.1,
        device="cpu",
        torch_dtype="float32",
        model_id="fake/model",
        model_revision=None,
    )
    with pytest.raises(OutputPersistenceError):
        service.persist(request, generated)
