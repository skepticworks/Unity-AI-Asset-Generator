"""Post-generation image processing pipeline for sprites/icons and tileable textures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.domain.enums import TransparencyStrategy
from unity_ai_assets.processing.alpha_cleanup import AlphaCleanupParams, apply_alpha_cleanup
from unity_ai_assets.processing.seam_analysis import SeamAnalysisResult
from unity_ai_assets.processing.seam_inpaint import SeamInpainter, UnavailableSeamInpainter
from unity_ai_assets.processing.tileable import (
    TileableProcessingParams,
    apply_tileable_processing,
)
from unity_ai_assets.processing.wrap_diagnostics import WrapDiscontinuityResult

if TYPE_CHECKING:
    from unity_ai_assets.processing.background_removal import ImageBackgroundRemover


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Outcome of optional transparency + tileable post-processing."""

    image: Image.Image
    original_image: Image.Image | None
    transparency_strategy: str
    background_removal_applied: bool
    background_removal_implementation: str | None
    alpha_cleanup_applied: bool
    alpha_threshold: int
    alpha_feather: int
    remove_near_transparent: bool
    zero_rgb_when_transparent: bool
    tileable: bool = False
    seam_correction_applied: bool = False
    palette_reduction_applied: bool = False
    seam_blend_width: int = 64
    palette_color_count: int = 16
    seam_score_before: float | None = None
    seam_score_after: float | None = None
    horizontal_seam_score: float | None = None
    vertical_seam_score: float | None = None
    horizontal_wrap_discontinuity: float | None = None
    vertical_wrap_discontinuity: float | None = None
    seam_inpaint_implementation: str | None = None


def _seam_fields(
    before: SeamAnalysisResult | None,
    after: SeamAnalysisResult | None,
) -> dict[str, float | None]:
    source = after or before
    return {
        "seam_score_before": None if before is None else before.combined_score,
        "seam_score_after": None if after is None else after.combined_score,
        "horizontal_seam_score": None if source is None else source.horizontal_score,
        "vertical_seam_score": None if source is None else source.vertical_score,
    }


def _wrap_fields(
    before: WrapDiscontinuityResult | None,
    after: WrapDiscontinuityResult | None,
) -> dict[str, float | None]:
    source = after or before
    return {
        "horizontal_wrap_discontinuity": None if source is None else source.horizontal_ratio,
        "vertical_wrap_discontinuity": None if source is None else source.vertical_ratio,
    }


class ImageProcessingPipeline:
    """Common post-processing stage after text-to-image inference."""

    def __init__(
        self,
        background_remover: ImageBackgroundRemover,
        seam_inpainter: SeamInpainter | None = None,
    ) -> None:
        self._background_remover = background_remover
        self._seam_inpainter = seam_inpainter or UnavailableSeamInpainter()

    @property
    def background_remover(self) -> ImageBackgroundRemover:
        return self._background_remover

    @property
    def seam_inpainter(self) -> SeamInpainter:
        return self._seam_inpainter

    def process(
        self,
        image: Image.Image,
        *,
        transparency_strategy: str,
        alpha_params: AlphaCleanupParams,
        preserve_original: bool = True,
        tileable_params: TileableProcessingParams | None = None,
        exclusive_vram: bool = False,
    ) -> ProcessingResult:
        """Apply transparency strategy, then optional tileable steps."""
        strategy = (transparency_strategy or TransparencyStrategy.NONE.value).strip().lower()
        original = image.copy() if preserve_original else None
        tileable = tileable_params or TileableProcessingParams()

        if strategy == TransparencyStrategy.NONE.value:
            working = image
            bg_applied = False
            bg_impl = None
            alpha_applied = False
        elif strategy != TransparencyStrategy.BACKGROUND_REMOVAL.value:
            raise AppError(
                f"Transparency strategy '{strategy}' is not supported.",
                code=AppErrorCode.TRANSPARENCY_STRATEGY_UNSUPPORTED,
            )
        else:
            if not self._background_remover.available:
                raise AppError(
                    "Background removal is required by the selected transparency strategy "
                    "but is unavailable on this backend.",
                    code=AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE,
                )
            try:
                rgba = self._background_remover.remove_background(image)
            except AppError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise AppError(
                    "Background removal failed while processing the generated image.",
                    code=AppErrorCode.BACKGROUND_REMOVAL_FAILED,
                ) from exc
            if rgba.size != image.size:
                raise AppError(
                    "Background removal changed image dimensions.",
                    code=AppErrorCode.BACKGROUND_REMOVAL_FAILED,
                )
            working = apply_alpha_cleanup(rgba, alpha_params)
            bg_applied = True
            bg_impl = self._background_remover.implementation_id
            alpha_applied = True

        if (
            exclusive_vram
            and bg_applied
            and tileable.apply_seam_correction
        ):
            unload = getattr(self._background_remover, "unload_weights", None)
            if callable(unload):
                unload()

        tileable_result = apply_tileable_processing(
            working,
            tileable,
            preserve_original=False,
            seam_inpainter=self._seam_inpainter,
        )
        final = tileable_result.image
        any_mutation = bg_applied or tileable_result.seam_correction_applied or (
            tileable_result.palette_reduction_applied
        )
        preserved = original if (preserve_original and any_mutation) else None
        seam = _seam_fields(
            tileable_result.seam_analysis_before,
            tileable_result.seam_analysis_after,
        )
        wrap = _wrap_fields(tileable_result.wrap_before, tileable_result.wrap_after)

        return ProcessingResult(
            image=final,
            original_image=preserved,
            transparency_strategy=strategy,
            background_removal_applied=bg_applied,
            background_removal_implementation=bg_impl,
            alpha_cleanup_applied=alpha_applied,
            alpha_threshold=alpha_params.alpha_threshold,
            alpha_feather=alpha_params.alpha_feather,
            remove_near_transparent=alpha_params.remove_near_transparent,
            zero_rgb_when_transparent=alpha_params.zero_rgb_when_transparent,
            tileable=tileable.tileable or tileable_result.tileable,
            seam_correction_applied=tileable_result.seam_correction_applied,
            palette_reduction_applied=tileable_result.palette_reduction_applied,
            seam_blend_width=tileable.seam_blend_width,
            palette_color_count=tileable.palette_color_count,
            seam_score_before=seam["seam_score_before"],
            seam_score_after=seam["seam_score_after"],
            horizontal_seam_score=seam["horizontal_seam_score"],
            vertical_seam_score=seam["vertical_seam_score"],
            horizontal_wrap_discontinuity=wrap["horizontal_wrap_discontinuity"],
            vertical_wrap_discontinuity=wrap["vertical_wrap_discontinuity"],
            seam_inpaint_implementation=tileable_result.seam_inpaint_implementation,
        )
