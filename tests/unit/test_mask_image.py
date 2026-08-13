"""Unit tests for inpainting mask validation, semantics, and alignment."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import GenerationRequestInvalidError
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.domain.image_upload import luminance_ignoring_alpha
from unity_ai_assets.domain.mask_image import (
    MASK_CONVENTION_ID,
    assert_source_mask_dimensions_match,
    decode_mask_image_base64,
    prepare_inpaint_mask,
    prepare_inpaint_source,
    validate_mask_image,
)


def _png_bytes(
    width: int = 64,
    height: int = 64,
    *,
    mode: str = "L",
    color: int | tuple[int, ...] = 255,
) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _rgba_mask_bytes(
    width: int = 64,
    height: int = 64,
    *,
    rgb: tuple[int, int, int] = (255, 255, 255),
    alpha: int = 0,
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), color=(*rgb, alpha)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_validate_luminance_mask() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    raw = _png_bytes(64, 64, color=255)
    validated = validate_mask_image(raw_bytes=raw, policy=policy, media_type="image/png")
    assert validated.image.mode == "L"
    assert validated.image.size == (64, 64)
    assert validated.metadata.format == "png"
    assert validated.image.getextrema() == (255, 255)


def test_rejects_all_black_mask() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_mask_image(raw_bytes=_png_bytes(64, 64, color=0), policy=policy)
    assert "mask_image" in exc.value.field_issues
    assert exc.value.field_issues["mask_image"][0].code.value == "VALUE_INVALID"


def test_rejects_corrupt_mask() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_mask_image(raw_bytes=b"not-an-image", policy=policy)
    assert exc.value.field_issues["mask_image"][0].code.value == "FORMAT_INVALID"


def test_rejects_oversize_mask() -> None:
    policy = GenerationPolicy.from_settings(Settings(max_mask_image_bytes=32))
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_mask_image(raw_bytes=_png_bytes(), policy=policy)
    assert exc.value.field_issues["mask_image"][0].code.value == "VALUE_ABOVE_MAXIMUM"


def test_rejects_invalid_mask_dimensions() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError) as exc:
        validate_mask_image(raw_bytes=_png_bytes(width=13, height=64), policy=policy)
    assert "mask_image.width" in exc.value.field_issues


def test_rejects_invalid_mask_base64() -> None:
    with pytest.raises(GenerationRequestInvalidError) as exc:
        decode_mask_image_base64("%%%not-base64%%%")
    assert "mask_image.content_base64" in exc.value.field_issues


def test_mask_alpha_does_not_change_semantics() -> None:
    """Transparent white RGBA must still be a white (inpaint) mask."""
    policy = GenerationPolicy.from_settings(Settings())
    raw = _rgba_mask_bytes(rgb=(255, 255, 255), alpha=0)
    validated = validate_mask_image(raw_bytes=raw, policy=policy)
    assert validated.image.getpixel((0, 0)) == 255


def test_mask_transparent_black_stays_keep() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    # Mix: opaque white inpaint region plus fully transparent black (keep).
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(16):
        for y in range(16):
            image.putpixel((x, y), (255, 255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    validated = validate_mask_image(raw_bytes=buffer.getvalue(), policy=policy)
    assert validated.image.getpixel((0, 0)) == 255
    assert validated.image.getpixel((32, 32)) == 0


def test_luminance_ignores_alpha_channel() -> None:
    rgba = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
    rgba.putpixel((0, 0), (255, 255, 255, 0))
    gray = luminance_ignoring_alpha(rgba)
    assert gray.getpixel((0, 0)) == 255
    assert gray.getpixel((1, 1)) == 0


def test_dimension_mismatch_is_rejected() -> None:
    with pytest.raises(GenerationRequestInvalidError) as exc:
        assert_source_mask_dimensions_match(
            source_width=64,
            source_height=64,
            mask_width=64,
            mask_height=32,
        )
    assert "mask_image" in exc.value.field_issues


def test_prepare_mask_resizes_predictably() -> None:
    mask = Image.new("L", (64, 32), color=255)
    first = prepare_inpaint_mask(mask, 128, 64)
    second = prepare_inpaint_mask(mask, 128, 64)
    assert first.size == (128, 64)
    assert first.mode == "L"
    assert list(first.getdata()) == list(second.getdata())


def test_prepare_source_composites_alpha_on_black() -> None:
    source = Image.new("RGBA", (16, 16), (255, 0, 0, 0))
    rgb = prepare_inpaint_source(source, 16, 16)
    assert rgb.mode == "RGB"
    assert rgb.getpixel((0, 0)) == (0, 0, 0)


def test_mask_convention_id_is_stable() -> None:
    assert MASK_CONVENTION_ID == "white_inpaints"
