"""Central thresholds for tileable offset, mask, border protection, and diagnostics."""

from __future__ import annotations

# Fixed workflow size for seamless repair (Milestone 6 AI path).
TILEABLE_TARGET_SIZE: int = 512
CIRCULAR_OFFSET_PX: int = 256  # half of 512; moves seams to center

# Center-cross inpainting mask width (pixels). Must leave protected border intact.
DEFAULT_SEAM_WIDTH: int = 64
MIN_SEAM_WIDTH: int = 8
MAX_SEAM_WIDTH: int = 128

# Exterior pixels restored after inpaint so wrap edges stay exact.
PROTECTED_BORDER_PX: int = 4

# Soft feather for the cross mask (pixels from hard core to full transparent).
DEFAULT_MASK_FEATHER_PX: int = 8

# Legacy soft-blend defaults retained for offline algorithm tests only.
DEFAULT_SEAM_BLEND_WIDTH: int = 8
MIN_SEAM_BLEND_WIDTH: int = 1
MAX_SEAM_BLEND_WIDTH: int = 64

# Offset preview (UI) uses half-dimension shift; matches CIRCULAR_OFFSET_PX at 512.
OFFSET_PREVIEW_FRACTION: float = 0.5

# Wrap-mode preview grid.
DEFAULT_TILE_PREVIEW_REPEAT: int = 3

# Palette defaults (unchanged).
DEFAULT_PALETTE_COLOR_COUNT: int = 16
MIN_PALETTE_COLOR_COUNT: int = 2
MAX_PALETTE_COLOR_COUNT: int = 256

# Legacy edge-RGB score thresholds (still used by analyze_seams).
SEAM_SCORE_EXCELLENT_MAX: float = 0.05
SEAM_SCORE_ACCEPTABLE_MAX: float = 0.15
SEAM_SCORE_POOR_MIN: float = 0.15
SEAM_RGB_NORMALIZER: float = 255.0
SEAM_EDGE_PERCENTILE: float = 95.0

# Default inpaint prompt / negative for seam repair.
DEFAULT_SEAM_INPAINT_PROMPT: str = (
    "Repair the masked seam so the surrounding material continues naturally through it. "
    "Preserve the existing texture's scale, color, lighting, detail density, and structure. "
    "Do not introduce objects, borders, text, focal points, shadows, or large new features."
)
DEFAULT_SEAM_INPAINT_NEGATIVE: str = (
    "border, frame, text, logo, watermark, object, character, vignette, "
    "hard seam, grid, tiled panels, mosaic"
)
