"""Modular seam correction for tileable textures (nondestructive helpers).

Correction blends wrapped edge strips and does **not** guarantee a perfectly
seamless result. Callers must preserve the original asset separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from unity_ai_assets.processing.seam_thresholds import (
    DEFAULT_SEAM_BLEND_WIDTH,
    MAX_SEAM_BLEND_WIDTH,
    MIN_SEAM_BLEND_WIDTH,
)


@dataclass(frozen=True, slots=True)
class SeamCorrectionParams:
    """Parameters for a seam-correction pass."""

    blend_width: int = DEFAULT_SEAM_BLEND_WIDTH
    correct_horizontal: bool = True
    correct_vertical: bool = True


class SeamCorrectionAlgorithm(Protocol):
    """Pluggable correction strategy."""

    algorithm_id: str

    def apply(self, image: Image.Image, params: SeamCorrectionParams) -> Image.Image: ...


def _clamp_blend_width(value: int, size: int) -> int:
    width = max(MIN_SEAM_BLEND_WIDTH, min(MAX_SEAM_BLEND_WIDTH, int(value)))
    # Keep blend from consuming more than half the dimension.
    return max(1, min(width, max(1, size // 2)))


def _lerp_channel(a: int, b: int, t: float) -> int:
    return int(round(a * (1.0 - t) + b * t))


def _blend_pixels(
    left: tuple[int, ...],
    right: tuple[int, ...],
    t: float,
) -> tuple[int, ...]:
    channels = [_lerp_channel(left[i], right[i], t) for i in range(len(left))]
    return tuple(channels)


class SoftEdgeBlendCorrection:
    """Cross-fade opposite edges across a wrapped blend strip.

    Processes a copy of the source; the input image is never mutated.
    """

    algorithm_id = "soft_edge_blend"

    def apply(self, image: Image.Image, params: SeamCorrectionParams) -> Image.Image:
        working = image.copy()
        if params.correct_horizontal:
            working = self._blend_horizontal(working, params.blend_width)
        if params.correct_vertical:
            working = self._blend_vertical(working, params.blend_width)
        return working

    def _blend_horizontal(self, image: Image.Image, blend_width: int) -> Image.Image:
        width, height = image.size
        strip = _clamp_blend_width(blend_width, width)
        pixels = list(image.getdata())
        bands = len(pixels[0]) if pixels else 0
        if bands == 0:
            return image.copy()

        result = list(pixels)
        for y in range(height):
            for i in range(strip):
                # Weight increases toward the absolute edge.
                t = (i + 1) / (strip + 1)
                left_idx = y * width + i
                right_idx = y * width + (width - 1 - i)
                left = pixels[left_idx]
                right = pixels[right_idx]
                # Pull left edge toward right-edge colors and vice versa.
                result[left_idx] = _blend_pixels(left, right, t * 0.5)
                result[right_idx] = _blend_pixels(right, left, t * 0.5)

        out = Image.new(image.mode, image.size)
        out.putdata(result)
        return out

    def _blend_vertical(self, image: Image.Image, blend_width: int) -> Image.Image:
        width, height = image.size
        strip = _clamp_blend_width(blend_width, height)
        pixels = list(image.getdata())
        if not pixels:
            return image.copy()

        result = list(pixels)
        for x in range(width):
            for i in range(strip):
                t = (i + 1) / (strip + 1)
                top_idx = i * width + x
                bottom_idx = (height - 1 - i) * width + x
                top = pixels[top_idx]
                bottom = pixels[bottom_idx]
                result[top_idx] = _blend_pixels(top, bottom, t * 0.5)
                result[bottom_idx] = _blend_pixels(bottom, top, t * 0.5)

        out = Image.new(image.mode, image.size)
        out.putdata(result)
        return out


DEFAULT_SEAM_CORRECTOR: SeamCorrectionAlgorithm = SoftEdgeBlendCorrection()


def correct_seams(
    image: Image.Image,
    params: SeamCorrectionParams | None = None,
    *,
    algorithm: SeamCorrectionAlgorithm | None = None,
) -> Image.Image:
    """Apply seam correction to a copy of ``image``; never mutates the original."""
    resolved = params or SeamCorrectionParams()
    corrector = algorithm or DEFAULT_SEAM_CORRECTOR
    # Explicit copy boundary so callers can assert identity preservation.
    source = image.copy()
    return corrector.apply(source, resolved)
