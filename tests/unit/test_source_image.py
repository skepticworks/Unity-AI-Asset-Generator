"""Unit tests for img2img source-image decoding and validation."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import GenerationRequestInvalidError
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.domain.source_image import (
    decode_source_image_base64,
    prepare_init_image,
    validate_source_image,
)


def _png_bytes(
    width: int = 64,
    height: int = 64,
    color: tuple[int, int, int] = (10, 20, 30),
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_bytes(width: int = 64, height: int = 64) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(40, 50, 60)).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def test_validate_png_source_image() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    raw = _png_bytes(64, 64)
    validated = validate_source_image(raw_bytes=raw, policy=policy, media_type="image/png")
    assert validated.image.mode == "RGB"
    assert validated.image.size == (64, 64)
    assert validated.metadata.format == "png"
    assert validated.metadata.media_type == "image/png"
    assert validated.metadata.original_width == 64
    assert validated.metadata.byte_size == len(raw)
    assert len(validated.metadata.sha256) == 64


def test_validate_jpeg_source_image() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    validated = validate_source_image(raw_bytes=_jpeg_bytes(), policy=policy)
    assert validated.metadata.format == "jpeg"
    assert validated.metadata.media_type == "image/jpeg"


def test_rejects_corrupt_source_image() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_source_image(raw_bytes=b"not-an-image", policy=policy)
    assert "source_image" in exc.value.field_issues
    assert exc.value.field_issues["source_image"][0].code.value == "FORMAT_INVALID"


def test_rejects_oversize_source_image() -> None:
    policy = GenerationPolicy.from_settings(Settings(max_source_image_bytes=32))
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_source_image(raw_bytes=_png_bytes(), policy=policy)
    assert exc.value.field_issues["source_image"][0].code.value == "VALUE_ABOVE_MAXIMUM"


def test_rejects_invalid_source_dimensions() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_source_image(raw_bytes=_png_bytes(width=13, height=64), policy=policy)
    assert "source_image.width" in exc.value.field_issues


def test_rejects_media_type_mismatch() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_source_image(
            raw_bytes=_png_bytes(),
            policy=policy,
            media_type="image/jpeg",
        )
    assert "source_image.media_type" in exc.value.field_issues


def test_rejects_invalid_base64() -> None:
    with pytest.raises(GenerationRequestInvalidError) as exc:
        decode_source_image_base64("%%%not-base64%%%")
    assert "source_image.content_base64" in exc.value.field_issues


def test_prepare_init_image_resizes_deterministically() -> None:
    source = Image.new("RGB", (64, 32), color=(1, 2, 3))
    first = prepare_init_image(source, 128, 64)
    second = prepare_init_image(source, 128, 64)
    assert first.size == (128, 64)
    assert list(first.getdata()) == list(second.getdata())
