"""Masked inpainting generation tests (distinct from img2img and IP-Adapter)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import GenerationRequestInvalidError, OperationUnsupportedError
from unity_ai_assets.domain.generation_manifest import parse_manifest_payload
from unity_ai_assets.domain.mask_image import MASK_CONVENTION_ID
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.services.generation_service import GenerationService
from unity_ai_assets.services.output_service import OutputService, sha256_file


def _png_base64(
    width: int = 64,
    height: int = 64,
    color: tuple[int, int, int] = (200, 10, 10),
    mode: str = "RGB",
) -> str:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), color=color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _mask_base64(
    width: int = 64,
    height: int = 64,
    *,
    inpaint_rect: tuple[int, int, int, int] = (0, 0, 32, 32),
) -> str:
    mask = Image.new("L", (width, height), color=0)
    for x in range(inpaint_rect[0], inpaint_rect[2]):
        for y in range(inpaint_rect[1], inpaint_rect[3]):
            mask.putpixel((x, y), 255)
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.fixture
def inpaint_service(tmp_path: Path) -> tuple[GenerationService, FakeImageGenerationBackend]:
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
        app_version="0.8.0-test",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    return GenerationService(backend, output, settings), backend


def test_inpainting_generates_and_records_metadata(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = inpaint_service
    result = gen.generate_texture(
        prompt="replace the rusted patch",
        width=64,
        height=64,
        steps=1,
        seed=99,
        operation="inpainting",
        source_image_base64=_png_base64(),
        source_image_media_type="image/png",
        mask_image_base64=_mask_base64(),
        mask_image_media_type="image/png",
        denoising_strength=0.4,
        output_name="inpaint_metal",
    )
    assert result.operation == "inpainting"
    assert backend.calls[0].operation == "inpainting"
    assert backend.calls[0].denoising_strength == 0.4
    assert backend.calls[0].source_image is not None
    assert backend.calls[0].mask_image is not None
    assert backend.calls[0].source_image.size == (64, 64)
    assert backend.calls[0].mask_image.size == (64, 64)
    assert backend.calls[0].mask_convention == MASK_CONVENTION_ID

    payload = parse_manifest_payload(
        json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    )
    assert payload.generation.operation == "inpainting"
    assert payload.request.denoising_strength == 0.4
    assert payload.request.mask_convention == MASK_CONVENTION_ID
    assert payload.request.source_image is not None
    assert payload.request.mask_image is not None
    assert payload.request.mask_image.format == "png"
    assert payload.request.mask_image.width == 64
    assert payload.request.mask_image.sha256


def test_inpainting_is_reproducible_with_same_inputs(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = inpaint_service
    source = _png_base64(color=(12, 34, 56))
    mask = _mask_base64()
    kwargs = {
        "prompt": "same inpaint",
        "width": 64,
        "height": 64,
        "steps": 1,
        "seed": 12345,
        "operation": "inpainting",
        "source_image_base64": source,
        "mask_image_base64": mask,
        "denoising_strength": 0.55,
        "output_name": "same_a",
    }
    first = gen.generate_texture(**kwargs)
    kwargs["output_name"] = "same_b"
    second = gen.generate_texture(**kwargs)
    assert sha256_file(Path(first.image_path)) == sha256_file(Path(second.image_path))


def test_inpainting_keeps_unmasked_source_pixels(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = inpaint_service
    result = gen.generate_texture(
        prompt="keep the unmasked half",
        width=64,
        height=64,
        steps=1,
        seed=7,
        operation="inpainting",
        source_image_base64=_png_base64(color=(10, 20, 30)),
        mask_image_base64=_mask_base64(inpaint_rect=(0, 0, 32, 64)),
        denoising_strength=1.0,
        output_name="keep_right",
    )
    image = Image.open(result.image_path).convert("RGB")
    assert image.getpixel((48, 32)) == (10, 20, 30)
    assert image.getpixel((8, 32)) != (10, 20, 30)


def test_inpainting_rejects_when_backend_unsupported(tmp_path: Path) -> None:
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        output_directory=tmp_path / "generated",
    )
    (tmp_path / "generated").mkdir()
    backend = FakeImageGenerationBackend(inpainting_supported=False)
    service = GenerationService(
        backend,
        OutputService(settings.output_directory, app_version="0.8.0-test", model_family="unknown"),
        settings,
    )
    with pytest.raises(OperationUnsupportedError) as exc:
        service.generate_texture(
            prompt="should fail",
            width=64,
            height=64,
            steps=1,
            operation="inpainting",
            source_image_base64=_png_base64(),
            mask_image_base64=_mask_base64(),
            output_name="fail",
        )
    assert "not converted to image_to_image or text_to_image" in str(exc.value)
    assert backend.calls == []


def test_inpainting_requires_mask(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = inpaint_service
    with pytest.raises(GenerationRequestInvalidError) as exc:
        gen.generate_texture(
            prompt="missing mask",
            width=64,
            height=64,
            steps=1,
            operation="inpainting",
            source_image_base64=_png_base64(),
            output_name="missing",
        )
    assert "mask_image" in exc.value.field_issues
    assert backend.calls == []


def test_inpainting_rejects_dimension_mismatch(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = inpaint_service
    with pytest.raises(GenerationRequestInvalidError) as exc:
        gen.generate_texture(
            prompt="mismatched",
            width=64,
            height=64,
            steps=1,
            operation="inpainting",
            source_image_base64=_png_base64(64, 64),
            mask_image_base64=_mask_base64(32, 32),
            output_name="mismatch",
        )
    assert "mask_image" in exc.value.field_issues
    assert backend.calls == []


def test_img2img_rejects_mask(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = inpaint_service
    with pytest.raises(GenerationRequestInvalidError) as exc:
        gen.generate_texture(
            prompt="img2img with mask",
            width=64,
            height=64,
            steps=1,
            operation="image_to_image",
            source_image_base64=_png_base64(),
            mask_image_base64=_mask_base64(),
            output_name="nope",
        )
    assert "mask_image" in exc.value.field_issues
    assert backend.calls == []


def test_txt2img_rejects_mask(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = inpaint_service
    with pytest.raises(GenerationRequestInvalidError) as exc:
        gen.generate_texture(
            prompt="txt2img",
            width=64,
            height=64,
            steps=1,
            operation="text_to_image",
            mask_image_base64=_mask_base64(),
            output_name="txt",
        )
    assert "mask_image" in exc.value.field_issues
    assert backend.calls == []


def test_txt2img_still_works_without_mask(
    inpaint_service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = inpaint_service
    result = gen.generate_texture(
        prompt="plain texture",
        width=64,
        height=64,
        steps=1,
        seed=7,
        output_name="plain",
    )
    assert result.operation == "text_to_image"
    assert backend.calls[0].mask_image is None
    assert backend.calls[0].source_image is None
