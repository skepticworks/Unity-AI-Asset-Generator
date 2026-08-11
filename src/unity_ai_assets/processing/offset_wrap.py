"""Circular offset / wrap helpers shared by previews, analysis, and correction."""

from __future__ import annotations

from PIL import Image

from unity_ai_assets.processing.seam_thresholds import (
    DEFAULT_TILE_PREVIEW_REPEAT,
    OFFSET_PREVIEW_FRACTION,
)


def wrap_coordinate(value: int, size: int) -> int:
    """Wrap an integer coordinate into ``[0, size)``."""
    if size <= 0:
        raise ValueError("size must be positive")
    return value % size


def offset_shift_amounts(
    width: int,
    height: int,
    *,
    fraction: float = OFFSET_PREVIEW_FRACTION,
) -> tuple[int, int]:
    """Return (dx, dy) pixel shifts for an offset/seam-centering preview."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    dx = int(round(width * fraction)) % width
    dy = int(round(height * fraction)) % height
    return dx, dy


def circular_shift(image: Image.Image, dx: int, dy: int) -> Image.Image:
    """Shift pixels by ``(dx, dy)`` with toroidal wrapping (no empty borders).

    Positive ``dx`` moves content right; positive ``dy`` moves content down.
    The returned image is always a new copy. Source pixel ``(x, y)`` lands at
    ``((x + dx) % width, (y + dy) % height)``.
    """
    width, height = image.size
    if width == 0 or height == 0:
        raise ValueError("image must have positive dimensions")

    dx = wrap_coordinate(dx, width)
    dy = wrap_coordinate(dy, height)
    if dx == 0 and dy == 0:
        return image.copy()

    # Horizontal wrap: dest[x] comes from source[(x - dx) % w].
    if dx == 0:
        horizontal = image.copy()
    else:
        horizontal = Image.new(image.mode, (width, height))
        left_src = image.crop((width - dx, 0, width, height))
        right_src = image.crop((0, 0, width - dx, height))
        horizontal.paste(left_src, (0, 0))
        horizontal.paste(right_src, (dx, 0))

    if dy == 0:
        return horizontal

    # Vertical wrap: dest[y] comes from source[(y - dy) % h].
    result = Image.new(image.mode, (width, height))
    top_src = horizontal.crop((0, height - dy, width, height))
    bottom_src = horizontal.crop((0, 0, width, height - dy))
    result.paste(top_src, (0, 0))
    result.paste(bottom_src, (0, dy))
    return result


def offset_preview(image: Image.Image, *, fraction: float = OFFSET_PREVIEW_FRACTION) -> Image.Image:
    """Shift by ~50% on both axes so seams move toward the center."""
    dx, dy = offset_shift_amounts(image.width, image.height, fraction=fraction)
    return circular_shift(image, dx, dy)


def tiled_preview(
    image: Image.Image,
    *,
    repeats: int = DEFAULT_TILE_PREVIEW_REPEAT,
) -> Image.Image:
    """Compose an ``repeats x repeats`` tiled view (wrap-mode preview)."""
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    width, height = image.size
    canvas = Image.new(image.mode, (width * repeats, height * repeats))
    for ty in range(repeats):
        for tx in range(repeats):
            canvas.paste(image, (tx * width, ty * height))
    return canvas
