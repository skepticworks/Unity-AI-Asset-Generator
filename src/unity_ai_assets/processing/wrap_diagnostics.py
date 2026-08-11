"""Wrap discontinuity diagnostics based on cross-boundary vs internal gradients."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True, slots=True)
class WrapDiscontinuityResult:
    """Normalized wrap discontinuity relative to typical adjacent-pixel gradients.

    A value near 1.0 means the wrap boundary is about as continuous as a normal
    internal pixel transition. This is a diagnostic, not a perceptual guarantee.
    """

    horizontal_ratio: float
    vertical_ratio: float
    internal_mean_gradient: float
    horizontal_wrap_gradient: float
    vertical_wrap_gradient: float

    def format_report(self) -> str:
        return (
            f"Horizontal wrap discontinuity: {self.horizontal_ratio:.2f}x normal gradient\n"
            f"Vertical wrap discontinuity:   {self.vertical_ratio:.2f}x normal gradient"
        )


def _rgb_channel_distance(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    channels = min(3, len(a), len(b))
    if channels == 0:
        return 0.0
    return sum(abs(a[i] - b[i]) for i in range(channels)) / float(channels)


def _mean_internal_gradient(pixels: list[tuple[int, ...]], width: int, height: int) -> float:
    total = 0.0
    count = 0
    for y in range(height):
        row = y * width
        for x in range(width - 1):
            total += _rgb_channel_distance(pixels[row + x], pixels[row + x + 1])
            count += 1
    for y in range(height - 1):
        for x in range(width):
            total += _rgb_channel_distance(pixels[y * width + x], pixels[(y + 1) * width + x])
            count += 1
    if count == 0:
        return 0.0
    return total / count


def analyze_wrap_discontinuity(image: Image.Image) -> WrapDiscontinuityResult:
    """Compare wrap-edge gradients to typical adjacent-pixel gradients inside the image."""
    width, height = image.size
    if width < 2 or height < 2:
        raise ValueError("image must be at least 2x2")

    rgb = image.convert("RGB")
    pixels = list(rgb.getdata())

    internal = _mean_internal_gradient(pixels, width, height)

    horizontal_wrap = 0.0
    for y in range(height):
        left = pixels[y * width]
        right = pixels[y * width + (width - 1)]
        horizontal_wrap += _rgb_channel_distance(right, left)
    horizontal_wrap /= float(height)

    vertical_wrap = 0.0
    for x in range(width):
        top = pixels[x]
        bottom = pixels[(height - 1) * width + x]
        vertical_wrap += _rgb_channel_distance(bottom, top)
    vertical_wrap /= float(width)

    # Avoid division by zero on flat images: treat tiny internal gradients as 1.0 unit.
    baseline = internal if internal > 1e-6 else 1.0
    return WrapDiscontinuityResult(
        horizontal_ratio=horizontal_wrap / baseline,
        vertical_ratio=vertical_wrap / baseline,
        internal_mean_gradient=internal,
        horizontal_wrap_gradient=horizontal_wrap,
        vertical_wrap_gradient=vertical_wrap,
    )
