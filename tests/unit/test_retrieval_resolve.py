"""Unit tests for generation ID validation and artifact resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from unity_ai_assets.core.errors import GenerationNotFoundError, GenerationRequestInvalidError
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest
from unity_ai_assets.services.output_service import OutputService, validate_generation_id


@pytest.mark.parametrize(
    "bad",
    ["", "not-a-uuid", "../etc/passwd", "aaaa/bbbb", "abcd\\efgh"],
)
def test_validate_generation_id_rejects_invalid(bad: str) -> None:
    with pytest.raises(GenerationRequestInvalidError):
        validate_generation_id(bad)


def test_resolve_artifacts_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    service = OutputService(root, app_version="0.3.0")
    generation_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    request = GenerationRequest(
        prompt="x",
        negative_prompt="",
        width=32,
        height=32,
        steps=1,
        guidance_scale=1.0,
        seed=1,
        output_name="tex",
        generation_id=generation_id,
    )
    generated = GeneratedImage(
        image=Image.new("RGB", (32, 32), color=(1, 2, 3)),
        seed=1,
        width=32,
        height=32,
        elapsed_seconds=0.1,
        device="cpu",
        torch_dtype="float32",
        model_id="fake/model",
        model_revision=None,
    )
    service.persist(request, generated)
    artifacts = service.resolve_artifacts(generation_id)
    assert artifacts.image_path.is_file()
    assert artifacts.metadata_path.is_file()
    assert artifacts.metadata_path.name == "manifest.json"


def test_resolve_artifacts_missing(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    root.mkdir()
    service = OutputService(root, app_version="0.3.0")
    with pytest.raises(GenerationNotFoundError):
        service.resolve_artifacts("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
