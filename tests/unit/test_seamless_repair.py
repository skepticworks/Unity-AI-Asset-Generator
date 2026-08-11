"""Unit tests for AI seamless repair: offset, mask, border, preview, diagnostics."""

from __future__ import annotations

import pytest
from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.processing.offset_wrap import circular_shift, tiled_preview
from unity_ai_assets.processing.seam_inpaint import FakeSeamInpainter, UnavailableSeamInpainter
from unity_ai_assets.processing.seam_mask import (
    build_center_cross_mask,
    mask_touches_protected_border,
)
from unity_ai_assets.processing.seam_thresholds import (
    CIRCULAR_OFFSET_PX,
    PROTECTED_BORDER_PX,
    TILEABLE_TARGET_SIZE,
)
from unity_ai_assets.processing.seamless_repair import (
    SeamlessRepairParams,
    make_seamless_with_inpaint,
    preserve_and_restore_border,
)
from unity_ai_assets.processing.tileable import TileableProcessingParams, apply_tileable_processing
from unity_ai_assets.processing.wrap_diagnostics import analyze_wrap_discontinuity


def _gradient_512() -> Image.Image:
    """Non-uniform 512 texture with a strong left/right discontinuity."""
    image = Image.new("RGB", (TILEABLE_TARGET_SIZE, TILEABLE_TARGET_SIZE))
    for y in range(TILEABLE_TARGET_SIZE):
        for x in range(TILEABLE_TARGET_SIZE):
            image.putpixel(
                (x, y),
                (10, 20, 30) if x < TILEABLE_TARGET_SIZE // 2 else (200, 180, 40),
            )
    return image


def test_circular_offset_exactly_256() -> None:
    image = Image.new("RGB", (512, 512))
    for y in range(512):
        for x in range(512):
            image.putpixel((x, y), (x % 256, y % 256, 7))
    shifted = circular_shift(image, CIRCULAR_OFFSET_PX, CIRCULAR_OFFSET_PX)
    assert shifted.size == (512, 512)
    # Source (0,0) moves to (256,256)
    assert shifted.getpixel((256, 256)) == image.getpixel((0, 0))
    # Source (255,255) wraps to (511,511)
    assert shifted.getpixel((511, 511)) == image.getpixel((255, 255))
    # Original unchanged
    assert image.getpixel((0, 0)) == (0, 0, 7)


def test_center_cross_mask_location_and_protected_border() -> None:
    mask = build_center_cross_mask(512, seam_width=64, feather_px=0, protected_border=4)
    assert mask.size == (512, 512)
    assert mask.mode == "L"
    # Center should be masked
    assert mask.getpixel((256, 256)) == 255
    # Arms exist
    assert mask.getpixel((256, 100)) == 255
    assert mask.getpixel((100, 256)) == 255
    # Protected border never masked
    assert mask.getpixel((0, 0)) == 0
    assert mask.getpixel((511, 256)) == 0
    assert mask.getpixel((256, 0)) == 0
    assert not mask_touches_protected_border(mask, protected_border=4)


def test_feathered_mask_still_clears_protected_border() -> None:
    mask = build_center_cross_mask(512, seam_width=64, feather_px=8, protected_border=4)
    assert not mask_touches_protected_border(mask, protected_border=4)
    for x in range(512):
        assert mask.getpixel((x, 0)) == 0
        assert mask.getpixel((x, 511)) == 0
    for y in range(512):
        assert mask.getpixel((0, y)) == 0
        assert mask.getpixel((511, y)) == 0


def test_seamless_repair_preserves_size_and_border() -> None:
    source = _gradient_512()
    result = make_seamless_with_inpaint(source, FakeSeamInpainter(), SeamlessRepairParams(seam_width=64))
    assert result.image.size == (512, 512)
    offset = circular_shift(source, 256, 256)
    border = PROTECTED_BORDER_PX
    # Exterior border pixels identical to offset image
    for x in range(512):
        for y in range(border):
            assert result.image.getpixel((x, y)) == offset.getpixel((x, y))
            assert result.image.getpixel((x, 511 - y)) == offset.getpixel((x, 511 - y))
    for y in range(border, 512 - border):
        for x in range(border):
            assert result.image.getpixel((x, y)) == offset.getpixel((x, y))
            assert result.image.getpixel((511 - x, y)) == offset.getpixel((511 - x, y))


def test_preserve_and_restore_border_helper() -> None:
    original = Image.new("RGB", (16, 16), color=(1, 2, 3))
    repaired = Image.new("RGB", (16, 16), color=(9, 9, 9))
    restored = preserve_and_restore_border(original, repaired, border=2)
    assert restored.getpixel((0, 0)) == (1, 2, 3)
    assert restored.getpixel((8, 8)) == (9, 9, 9)


def test_tiled_preview_is_1536() -> None:
    tile = Image.new("RGB", (512, 512), color=(5, 6, 7))
    preview = tiled_preview(tile, repeats=3)
    assert preview.size == (1536, 1536)
    assert preview.getpixel((0, 0)) == (5, 6, 7)
    assert preview.getpixel((512, 512)) == (5, 6, 7)


def test_wrap_discontinuity_near_one_for_smooth_solid() -> None:
    solid = Image.new("RGB", (64, 64), color=(40, 50, 60))
    # Add tiny noise so internal gradient is non-zero
    solid.putpixel((10, 10), (41, 50, 60))
    result = analyze_wrap_discontinuity(solid)
    assert result.horizontal_ratio < 2.0
    assert result.vertical_ratio < 2.0
    assert "Horizontal wrap discontinuity" in result.format_report()


def test_wrap_discontinuity_high_for_hard_seam() -> None:
    image = Image.new("RGB", (32, 32))
    for y in range(32):
        for x in range(32):
            image.putpixel((x, y), (0, 0, 0) if x < 16 else (255, 255, 255))
    result = analyze_wrap_discontinuity(image)
    assert result.horizontal_ratio > 5.0


def test_inpaint_unavailable_does_not_silently_succeed() -> None:
    with pytest.raises(AppError) as exc:
        make_seamless_with_inpaint(_gradient_512(), UnavailableSeamInpainter("disabled"))
    assert exc.value.code == AppErrorCode.SEAM_INPAINT_UNAVAILABLE


def test_inpaint_failure_does_not_claim_success() -> None:
    with pytest.raises(AppError) as exc:
        make_seamless_with_inpaint(_gradient_512(), FakeSeamInpainter(fail=True))
    assert exc.value.code == AppErrorCode.SEAM_INPAINT_FAILED


def test_tileable_pipeline_uses_ai_path_and_preserves_original() -> None:
    source = _gradient_512()
    result = apply_tileable_processing(
        source,
        TileableProcessingParams(
            tileable=True,
            apply_seam_correction=True,
            seam_blend_width=64,
        ),
        preserve_original=True,
        seam_inpainter=FakeSeamInpainter(),
    )
    assert result.seam_correction_applied is True
    assert result.original_image is not None
    assert list(result.original_image.getdata()) == list(source.getdata())
    assert result.image.size == (512, 512)
    assert result.wrap_after is not None
    assert result.seam_inpaint_implementation == "fake:neighbor_fill"


def test_wrong_size_rejected() -> None:
    small = Image.new("RGB", (128, 128), color=(1, 2, 3))
    with pytest.raises(AppError) as exc:
        make_seamless_with_inpaint(small, FakeSeamInpainter())
    assert exc.value.code == AppErrorCode.GENERATION_REQUEST_INVALID
