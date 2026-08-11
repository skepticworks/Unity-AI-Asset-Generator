"""Ordered tileable post-processing: optional AI seamless repair then optional palette.

Seam correction uses circular offset + center-cross mask + local AI inpainting.
There is no silent soft-blend fallback when inpainting is requested.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.processing.palette import PaletteReductionParams, reduce_palette
from unity_ai_assets.processing.seam_analysis import SeamAnalysisResult, analyze_seams
from unity_ai_assets.processing.seam_inpaint import SeamInpainter, UnavailableSeamInpainter
from unity_ai_assets.processing.seam_thresholds import DEFAULT_SEAM_WIDTH
from unity_ai_assets.processing.seamless_repair import (
    SeamlessRepairParams,
    make_seamless_with_inpaint,
)
from unity_ai_assets.processing.wrap_diagnostics import WrapDiscontinuityResult


@dataclass(frozen=True, slots=True)
class TileableProcessingParams:
    """User/profile-configurable tileable processing knobs."""

    tileable: bool = False
    apply_seam_correction: bool = False
    seam_blend_width: int = DEFAULT_SEAM_WIDTH  # seam/cross mask width for AI repair
    palette_reduction_enabled: bool = False
    palette_color_count: int = 16
    inpaint_seed: int | None = None


@dataclass(frozen=True, slots=True)
class TileableProcessingResult:
    """Outcome of optional tileable post-processing."""

    image: Image.Image
    original_image: Image.Image | None
    tileable: bool
    seam_correction_applied: bool
    palette_reduction_applied: bool
    seam_blend_width: int
    palette_color_count: int
    seam_analysis_before: SeamAnalysisResult | None
    seam_analysis_after: SeamAnalysisResult | None
    wrap_before: WrapDiscontinuityResult | None = None
    wrap_after: WrapDiscontinuityResult | None = None
    seam_inpaint_implementation: str | None = None


def apply_tileable_processing(
    image: Image.Image,
    params: TileableProcessingParams,
    *,
    preserve_original: bool = True,
    seam_inpainter: SeamInpainter | None = None,
) -> TileableProcessingResult:
    """Apply modular tileable steps without mutating ``image``.

    Order: analyze → optional AI seamless repair → optional palette → re-analyze.
    """
    if not params.tileable and not params.apply_seam_correction and not params.palette_reduction_enabled:
        return TileableProcessingResult(
            image=image,
            original_image=None,
            tileable=False,
            seam_correction_applied=False,
            palette_reduction_applied=False,
            seam_blend_width=params.seam_blend_width,
            palette_color_count=params.palette_color_count,
            seam_analysis_before=None,
            seam_analysis_after=None,
        )

    original = image.copy() if preserve_original else None
    working = image.copy()
    before = analyze_seams(working) if params.tileable or params.apply_seam_correction else None
    wrap_before: WrapDiscontinuityResult | None = None
    wrap_after: WrapDiscontinuityResult | None = None
    implementation: str | None = None

    seam_applied = False
    if params.apply_seam_correction:
        inpainter = seam_inpainter or UnavailableSeamInpainter(
            reason="no seam inpainter configured"
        )
        repair = make_seamless_with_inpaint(
            working,
            inpainter,
            SeamlessRepairParams(
                seam_width=params.seam_blend_width,
                seed=params.inpaint_seed,
            ),
        )
        working = repair.image
        wrap_before = repair.wrap_before
        wrap_after = repair.wrap_after
        implementation = repair.implementation_id
        seam_applied = True
        # Edge RGB scores on the final (offset-space) tile.
        before = analyze_seams(repair.offset_image)
        after_edge = analyze_seams(working)
    else:
        after_edge = None

    palette_applied = False
    if params.palette_reduction_enabled:
        working = reduce_palette(
            working,
            PaletteReductionParams(
                enabled=True,
                color_count=params.palette_color_count,
            ),
        )
        palette_applied = True

    after = after_edge
    if after is None and (before is not None or seam_applied or palette_applied):
        after = analyze_seams(working)
    if palette_applied and wrap_after is None and (params.tileable or seam_applied):
        from unity_ai_assets.processing.wrap_diagnostics import analyze_wrap_discontinuity

        wrap_after = analyze_wrap_discontinuity(working)

    if not seam_applied and not palette_applied:
        return TileableProcessingResult(
            image=image,
            original_image=None,
            tileable=params.tileable,
            seam_correction_applied=False,
            palette_reduction_applied=False,
            seam_blend_width=params.seam_blend_width,
            palette_color_count=params.palette_color_count,
            seam_analysis_before=before,
            seam_analysis_after=after,
            wrap_before=wrap_before,
            wrap_after=wrap_after,
        )

    return TileableProcessingResult(
        image=working,
        original_image=original,
        tileable=params.tileable or seam_applied or palette_applied,
        seam_correction_applied=seam_applied,
        palette_reduction_applied=palette_applied,
        seam_blend_width=params.seam_blend_width,
        palette_color_count=params.palette_color_count,
        seam_analysis_before=before,
        seam_analysis_after=after,
        wrap_before=wrap_before,
        wrap_after=wrap_after,
        seam_inpaint_implementation=implementation,
    )
