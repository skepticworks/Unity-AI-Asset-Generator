"""Image-to-image generation tests (init/source image, not reference conditioning)."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import GenerationRequestInvalidError, OperationUnsupportedError
from unity_ai_assets.domain.generation_manifest import parse_manifest_payload
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.services.generation_service import GenerationService
from unity_ai_assets.services.output_service import OutputService, sha256_file


def _png_base64(
    width: int = 64,
    height: int = 64,
    color: tuple[int, int, int] = (200, 10, 10),
) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.fixture
def img2img_service(tmp_path: Path) -> tuple[GenerationService, FakeImageGenerationBackend]:
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        output_directory=tmp_path / "generated",
        max_width=1024,
        max_height=1024,
    )
    (tmp_path / "generated").mkdir()
    backend = FakeImageGenerationBackend()
    output = OutputService(
        settings.output_directory,
        app_version="0.7.0-test",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    return GenerationService(backend, output, settings), backend


def test_img2img_generates_and_records_metadata(
    img2img_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = img2img_service
    result = gen.generate_texture(
        prompt="variation of rusted metal",
        width=64,
        height=64,
        steps=1,
        seed=99,
        operation="image_to_image",
        source_image_base64=_png_base64(),
        source_image_media_type="image/png",
        denoising_strength=0.4,
        output_name="metal_var",
    )
    assert result.operation == "image_to_image"
    assert backend.calls[0].operation == "image_to_image"
    assert backend.calls[0].denoising_strength == 0.4
    assert backend.calls[0].source_image is not None
    assert backend.calls[0].source_image.size == (64, 64)

    payload = parse_manifest_payload(
        __import__("json").loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    )
    assert payload.generation.operation == "image_to_image"
    assert payload.request.denoising_strength == 0.4
    assert payload.request.source_image is not None
    assert payload.request.source_image.format == "png"
    assert payload.request.source_image.width == 64
    assert payload.request.source_image.height == 64
    assert payload.request.source_image.sha256


def test_img2img_is_reproducible_with_same_inputs(
    img2img_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = img2img_service
    encoded = _png_base64(color=(12, 34, 56))
    kwargs = {
        "prompt": "same variation",
        "width": 64,
        "height": 64,
        "steps": 1,
        "seed": 12345,
        "operation": "image_to_image",
        "source_image_base64": encoded,
        "denoising_strength": 0.55,
        "output_name": "same_a",
    }
    first = gen.generate_texture(**kwargs)
    kwargs["output_name"] = "same_b"
    second = gen.generate_texture(**kwargs)
    assert sha256_file(Path(first.image_path)) == sha256_file(Path(second.image_path))


def test_img2img_defaults_denoising_strength(
    img2img_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = img2img_service
    gen.generate_texture(
        prompt="default strength",
        width=64,
        height=64,
        steps=1,
        seed=1,
        operation="image_to_image",
        source_image_base64=_png_base64(),
        output_name="default_strength",
    )
    assert backend.calls[0].denoising_strength == 0.75


def test_img2img_rejects_when_backend_unsupported(tmp_path: Path) -> None:
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        output_directory=tmp_path / "generated",
    )
    (tmp_path / "generated").mkdir()
    backend = FakeImageGenerationBackend(image_to_image_supported=False)
    service = GenerationService(
        backend,
        OutputService(settings.output_directory, app_version="0.7.0-test", model_family="unknown"),
        settings,
    )
    with pytest.raises(OperationUnsupportedError) as exc:
        service.generate_texture(
            prompt="should fail",
            width=64,
            height=64,
            steps=1,
            operation="image_to_image",
            source_image_base64=_png_base64(),
            output_name="fail",
        )
    assert "not converted to text-to-image" in str(exc.value)
    assert backend.calls == []


def test_txt2img_rejects_source_image(
    img2img_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = img2img_service
    with pytest.raises(GenerationRequestInvalidError) as exc:
        gen.generate_texture(
            prompt="txt2img",
            width=64,
            height=64,
            steps=1,
            operation="text_to_image",
            source_image_base64=_png_base64(),
            output_name="txt",
        )
    assert "source_image" in exc.value.field_issues
    assert backend.calls == []


def test_txt2img_still_works_without_source(
    img2img_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = img2img_service
    result = gen.generate_texture(
        prompt="plain texture",
        width=64,
        height=64,
        steps=1,
        seed=7,
        output_name="plain",
    )
    assert result.operation == "text_to_image"
    assert backend.calls[0].source_image is None
    assert backend.calls[0].denoising_strength is None


def test_img2img_rejects_strength_out_of_range(
    img2img_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = img2img_service
    with pytest.raises(GenerationRequestInvalidError) as exc:
        gen.generate_texture(
            prompt="too strong",
            width=64,
            height=64,
            steps=1,
            operation="image_to_image",
            source_image_base64=_png_base64(),
            denoising_strength=1.5,
            output_name="strong",
        )
    assert "denoising_strength" in exc.value.field_issues


def test_img2img_requires_source_image(
    img2img_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = img2img_service
    with pytest.raises(GenerationRequestInvalidError) as exc:
        gen.generate_texture(
            prompt="missing source",
            width=64,
            height=64,
            steps=1,
            operation="image_to_image",
            output_name="missing",
        )
    assert "source_image" in exc.value.field_issues
