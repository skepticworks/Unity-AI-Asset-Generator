"""Unit tests for tileable wrap, seam analysis/correction, and palette reduction."""

from __future__ import annotations

from PIL import Image

from unity_ai_assets.processing.offset_wrap import circular_shift, offset_preview, tiled_preview
from unity_ai_assets.processing.palette import PaletteReductionParams, reduce_palette
from unity_ai_assets.processing.seam_analysis import analyze_seams
from unity_ai_assets.processing.seam_correction import SeamCorrectionParams, correct_seams
from unity_ai_assets.processing.tileable import TileableProcessingParams, apply_tileable_processing


def _solid(size: tuple[int, int], color: tuple[int, ...], mode: str = "RGB") -> Image.Image:
    return Image.new(mode, size, color=color)


def _gradient_with_seam(size: tuple[int, int] = (16, 16)) -> Image.Image:
    """Left half dark, right half bright — strong left/right seam."""
    image = Image.new("RGB", size)
    mid = size[0] // 2
    for y in range(size[1]):
        for x in range(size[0]):
            image.putpixel((x, y), (10, 10, 10) if x < mid else (200, 200, 200))
    return image


def test_circular_shift_wraps_without_empty_borders() -> None:
    image = Image.new("RGB", (4, 4))
    # Unique colors per pixel for tracking.
    for y in range(4):
        for x in range(4):
            image.putpixel((x, y), (x * 40, y * 40, 100))

    shifted = circular_shift(image, 1, 0)
    assert shifted.size == (4, 4)
    # Source (0,0)=(0,0,100) should land at (1,0)
    assert shifted.getpixel((1, 0)) == (0, 0, 100)
    # Source (3,0) wraps to (0,0)
    assert shifted.getpixel((0, 0)) == (120, 0, 100)
    # Original unchanged
    assert image.getpixel((0, 0)) == (0, 0, 100)


def test_offset_preview_centers_edges() -> None:
    image = _gradient_with_seam((8, 8))
    preview = offset_preview(image)
    assert preview.size == (8, 8)
    # After 50% shift, the vertical seam between dark/bright should appear near center.
    left_center = preview.getpixel((3, 4))
    right_center = preview.getpixel((4, 4))
    assert left_center != right_center


def test_tiled_preview_dimensions() -> None:
    image = _solid((8, 6), (1, 2, 3))
    tiled = tiled_preview(image, repeats=3)
    assert tiled.size == (24, 18)
    assert tiled.getpixel((0, 0)) == (1, 2, 3)
    assert tiled.getpixel((8, 6)) == (1, 2, 3)


def test_seamless_solid_has_zero_seam_scores() -> None:
    image = _solid((12, 10), (40, 50, 60))
    result = analyze_seams(image)
    assert result.horizontal_score == 0.0
    assert result.vertical_score == 0.0
    assert result.combined_score == 0.0
    assert result.quality_label == "excellent"


def test_horizontal_and_vertical_seam_scores() -> None:
    # Horizontal seam: left vs right mismatch
    horizontal = _gradient_with_seam((10, 8))
    h = analyze_seams(horizontal)
    assert h.horizontal_score > 0.2
    assert h.vertical_score == 0.0  # top/bottom match within columns

    # Vertical seam: top vs bottom mismatch
    vertical = Image.new("RGB", (8, 10))
    for y in range(10):
        for x in range(8):
            vertical.putpixel((x, y), (10, 10, 10) if y < 5 else (200, 20, 20))
    v = analyze_seams(vertical)
    assert v.vertical_score > 0.2
    assert v.horizontal_score == 0.0


def test_combined_seam_score_averages_axes() -> None:
    image = Image.new("RGB", (8, 8))
    for y in range(8):
        for x in range(8):
            # Both axes mismatched
            color = (0, 0, 0)
            if x >= 4:
                color = (color[0] + 255, color[1], color[2])
            if y >= 4:
                color = (color[0], color[1] + 255, color[2])
            # simplify: checker of edges
            image.putpixel((x, y), (255 if x >= 4 else 0, 255 if y >= 4 else 0, 0))
    scores = analyze_seams(image)
    expected = (scores.horizontal_score + scores.vertical_score) / 2.0
    assert abs(scores.combined_score - expected) < 1e-9


def test_seam_correction_does_not_mutate_original() -> None:
    image = _gradient_with_seam((16, 16))
    before = image.copy()
    corrected = correct_seams(image, SeamCorrectionParams(blend_width=4))
    assert list(image.getdata()) == list(before.getdata())
    assert corrected is not image
    assert list(corrected.getdata()) != list(image.getdata())


def test_seam_correction_reduces_horizontal_score() -> None:
    image = _gradient_with_seam((32, 16))
    before = analyze_seams(image)
    corrected = correct_seams(image, SeamCorrectionParams(blend_width=8))
    after = analyze_seams(corrected)
    assert after.horizontal_score < before.horizontal_score


def test_palette_reduction_preserves_dimensions_and_alpha() -> None:
    image = Image.new("RGBA", (24, 18), color=(10, 20, 30, 200))
    for y in range(18):
        for x in range(24):
            image.putpixel((x, y), ((x * 7) % 256, (y * 11) % 256, 40, 180 if x > 2 else 0))

    reduced = reduce_palette(
        image,
        PaletteReductionParams(enabled=True, color_count=8, dither=False),
    )
    assert reduced.size == (24, 18)
    assert reduced.mode == "RGBA"
    # Transparent pixels keep alpha 0
    assert reduced.getpixel((0, 0))[3] == 0
    assert reduced.getpixel((10, 10))[3] == 180


def test_palette_disabled_returns_copy() -> None:
    image = _solid((8, 8), (1, 2, 3))
    result = reduce_palette(image, PaletteReductionParams(enabled=False))
    assert result is not image
    assert list(result.getdata()) == list(image.getdata())


def test_tileable_pipeline_preserves_original_when_processing() -> None:
    from unity_ai_assets.processing.seam_inpaint import FakeSeamInpainter

    image = _gradient_with_seam((512, 512))
    result = apply_tileable_processing(
        image,
        TileableProcessingParams(
            tileable=True,
            apply_seam_correction=True,
            seam_blend_width=64,
            palette_reduction_enabled=True,
            palette_color_count=8,
        ),
        preserve_original=True,
        seam_inpainter=FakeSeamInpainter(),
    )
    assert result.original_image is not None
    assert list(result.original_image.getdata()) == list(image.getdata())
    assert result.seam_correction_applied is True
    assert result.palette_reduction_applied is True
    assert result.image.size == (512, 512)
    assert result.seam_inpaint_implementation == "fake:neighbor_fill"
