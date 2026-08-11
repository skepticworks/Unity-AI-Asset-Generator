"""Optional palette reduction for retro / stylized textures."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.processing.seam_thresholds import (
    DEFAULT_PALETTE_COLOR_COUNT,
    MAX_PALETTE_COLOR_COUNT,
    MIN_PALETTE_COLOR_COUNT,
)


@dataclass(frozen=True, slots=True)
class PaletteReductionParams:
    """Palette-reduction settings (disabled unless callers opt in)."""

    enabled: bool = False
    color_count: int = DEFAULT_PALETTE_COLOR_COUNT
    dither: bool = False


def _clamp_color_count(value: int) -> int:
    return max(MIN_PALETTE_COLOR_COUNT, min(MAX_PALETTE_COLOR_COUNT, int(value)))


def reduce_palette(
    image: Image.Image,
    params: PaletteReductionParams | None = None,
) -> Image.Image:
    """Quantize RGB(A) to a limited palette while preserving dimensions and alpha.

    When ``enabled`` is false, returns a copy of the input unchanged.
    Alpha is preserved from the source; only RGB channels are quantized.
    """
    resolved = params or PaletteReductionParams()
    if not resolved.enabled:
        return image.copy()

    color_count = _clamp_color_count(resolved.color_count)
    source = image.convert("RGBA")
    width, height = source.size
    alpha = source.getchannel("A")
    rgb = source.convert("RGB")

    # Pillow quantize: method=0 (median cut), no dither by default for deterministic look.
    dither_flag = Image.Dither.FLOYDSTEINBERG if resolved.dither else Image.Dither.NONE
    quantized = rgb.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT, dither=dither_flag)
    quantized_rgb = quantized.convert("RGB")

    result = Image.merge("RGBA", (*quantized_rgb.split(), alpha))
    if result.size != (width, height):
        raise RuntimeError("palette reduction changed image dimensions")
    return result
