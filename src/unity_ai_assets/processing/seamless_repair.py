"""Seamless tileable repair: circular offset → center-cross mask → local AI inpaint.

The repaired offset image is the final tile (no inverse offset). Soft-edge blending
is not used as a success path or silent fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.processing.offset_wrap import circular_shift
from unity_ai_assets.processing.seam_inpaint import SeamInpainter
from unity_ai_assets.processing.seam_mask import build_center_cross_mask
from unity_ai_assets.processing.seam_thresholds import (
    CIRCULAR_OFFSET_PX,
    DEFAULT_MASK_FEATHER_PX,
    DEFAULT_SEAM_INPAINT_NEGATIVE,
    DEFAULT_SEAM_INPAINT_PROMPT,
    DEFAULT_SEAM_WIDTH,
    PROTECTED_BORDER_PX,
    TILEABLE_TARGET_SIZE,
)
from unity_ai_assets.processing.wrap_diagnostics import (
    WrapDiscontinuityResult,
    analyze_wrap_discontinuity,
)


@dataclass(frozen=True, slots=True)
class SeamlessRepairParams:
    """Parameters for the AI seamless-repair workflow."""

    seam_width: int = DEFAULT_SEAM_WIDTH
    protected_border: int = PROTECTED_BORDER_PX
    feather_px: int = DEFAULT_MASK_FEATHER_PX
    offset_px: int = CIRCULAR_OFFSET_PX
    inpaint_steps: int = 20
    guidance_scale: float = 7.5
    seed: int | None = None
    prompt: str = DEFAULT_SEAM_INPAINT_PROMPT
    negative_prompt: str = DEFAULT_SEAM_INPAINT_NEGATIVE


@dataclass(frozen=True, slots=True)
class SeamlessRepairResult:
    """Outcome of seamless AI repair (offset space is final)."""

    image: Image.Image
    offset_image: Image.Image
    mask: Image.Image
    wrap_before: WrapDiscontinuityResult
    wrap_after: WrapDiscontinuityResult
    implementation_id: str


def _require_target_size(image: Image.Image) -> None:
    if image.size != (TILEABLE_TARGET_SIZE, TILEABLE_TARGET_SIZE):
        raise AppError(
            f"Seamless repair requires exactly {TILEABLE_TARGET_SIZE}x{TILEABLE_TARGET_SIZE} "
            f"(got {image.width}x{image.height}).",
            code=AppErrorCode.GENERATION_REQUEST_INVALID,
        )


def preserve_and_restore_border(
    original: Image.Image,
    repaired: Image.Image,
    *,
    border: int = PROTECTED_BORDER_PX,
) -> Image.Image:
    """Copy exterior ``border`` pixels from ``original`` onto ``repaired`` (new image)."""
    if original.size != repaired.size:
        raise AppError(
            "Border restore requires matching image sizes.",
            code=AppErrorCode.SEAM_INPAINT_FAILED,
        )
    width, height = original.size
    b = max(0, int(border))
    if b == 0:
        return repaired.copy()
    out = repaired.copy()
    # Top / bottom strips
    out.paste(original.crop((0, 0, width, b)), (0, 0))
    out.paste(original.crop((0, height - b, width, height)), (0, height - b))
    # Left / right strips (middle only to avoid double-writing corners)
    out.paste(original.crop((0, b, b, height - b)), (0, b))
    out.paste(original.crop((width - b, b, width, height - b)), (width - b, b))
    return out


def make_seamless_with_inpaint(
    image: Image.Image,
    inpainter: SeamInpainter,
    params: SeamlessRepairParams | None = None,
) -> SeamlessRepairResult:
    """Run the full seamless workflow; raises on inpaint failure (no blend fallback)."""
    resolved = params or SeamlessRepairParams()
    _require_target_size(image)
    if not inpainter.available:
        raise AppError(
            "Seam inpainting is required but unavailable on this backend.",
            code=AppErrorCode.SEAM_INPAINT_UNAVAILABLE,
        )

    source = image.copy()
    offset = circular_shift(source, resolved.offset_px, resolved.offset_px)
    wrap_before = analyze_wrap_discontinuity(offset)
    mask = build_center_cross_mask(
        TILEABLE_TARGET_SIZE,
        seam_width=resolved.seam_width,
        feather_px=resolved.feather_px,
        protected_border=resolved.protected_border,
    )

    try:
        repaired = inpainter.inpaint(
            offset,
            mask,
            prompt=resolved.prompt,
            negative_prompt=resolved.negative_prompt,
            steps=resolved.inpaint_steps,
            guidance_scale=resolved.guidance_scale,
            seed=resolved.seed,
        )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "Local seam inpainting failed.",
            code=AppErrorCode.SEAM_INPAINT_FAILED,
        ) from exc

    if repaired.size != (TILEABLE_TARGET_SIZE, TILEABLE_TARGET_SIZE):
        raise AppError(
            "Seam inpainting changed image dimensions.",
            code=AppErrorCode.SEAM_INPAINT_FAILED,
        )

    final = preserve_and_restore_border(
        offset, repaired, border=resolved.protected_border
    )
    wrap_after = analyze_wrap_discontinuity(final)
    return SeamlessRepairResult(
        image=final,
        offset_image=offset,
        mask=mask,
        wrap_before=wrap_before,
        wrap_after=wrap_after,
        implementation_id=inpainter.implementation_id,
    )
