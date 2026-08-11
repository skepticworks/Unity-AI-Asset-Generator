"""Center-cross inpainting mask for circular-offset seam repair."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from unity_ai_assets.processing.seam_thresholds import (
    DEFAULT_MASK_FEATHER_PX,
    DEFAULT_SEAM_WIDTH,
    MAX_SEAM_WIDTH,
    MIN_SEAM_WIDTH,
    PROTECTED_BORDER_PX,
    TILEABLE_TARGET_SIZE,
)


def clamp_seam_width(value: int, *, size: int = TILEABLE_TARGET_SIZE) -> int:
    """Clamp seam width so the cross cannot reach the protected exterior border."""
    width = max(MIN_SEAM_WIDTH, min(MAX_SEAM_WIDTH, int(value)))
    # Cross half-width must leave protected border + 1 px margin on each side of center.
    max_half = (size // 2) - PROTECTED_BORDER_PX - 1
    if max_half < 1:
        raise ValueError("image too small for protected border and seam mask")
    half = min(width // 2, max_half)
    return max(MIN_SEAM_WIDTH, half * 2)


def build_center_cross_mask(
    size: int = TILEABLE_TARGET_SIZE,
    *,
    seam_width: int = DEFAULT_SEAM_WIDTH,
    feather_px: int = DEFAULT_MASK_FEATHER_PX,
    protected_border: int = PROTECTED_BORDER_PX,
) -> Image.Image:
    """Build an L-mode mask (0=keep, 255=inpaint) as a feathered center cross.

    The cross is centered at ``(size/2, size/2)``. Masked pixels never enter the
    protected exterior border band.
    """
    if size < 2:
        raise ValueError("size must be at least 2")
    width = clamp_seam_width(seam_width, size=size)
    half = width // 2
    center = size // 2
    border = max(0, int(protected_border))

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)

    # Vertical arm: full height except protected borders; width around center x.
    x0 = max(border, center - half)
    x1 = min(size - border - 1, center + half - 1)
    y0 = border
    y1 = size - border - 1
    if x1 >= x0 and y1 >= y0:
        draw.rectangle([x0, y0, x1, y1], fill=255)

    # Horizontal arm: full width except protected borders; height around center y.
    y0h = max(border, center - half)
    y1h = min(size - border - 1, center + half - 1)
    x0h = border
    x1h = size - border - 1
    if x1h >= x0h and y1h >= y0h:
        draw.rectangle([x0h, y0h, x1h, y1h], fill=255)

    feather = max(0, int(feather_px))
    if feather > 0:
        # Gaussian blur softens mask edges for natural transitions.
        mask = mask.filter(ImageFilter.GaussianBlur(radius=float(feather)))
        # Re-zero protected border after blur so feather never leaks to exterior.
        pixels = mask.load()
        assert pixels is not None
        for y in range(size):
            for x in range(size):
                if x < border or y < border or x >= size - border or y >= size - border:
                    pixels[x, y] = 0

    return mask


def mask_touches_protected_border(
    mask: Image.Image,
    *,
    protected_border: int = PROTECTED_BORDER_PX,
) -> bool:
    """Return True if any non-zero mask pixel intersects the protected border."""
    width, height = mask.size
    border = max(0, int(protected_border))
    gray = mask.convert("L")
    pixels = gray.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 0:
                continue
            if x < border or y < border or x >= width - border or y >= height - border:
                return True
    return False
