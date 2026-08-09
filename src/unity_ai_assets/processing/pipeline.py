"""Post-generation image processing pipeline for sprites/icons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.domain.enums import TransparencyStrategy
from unity_ai_assets.processing.alpha_cleanup import AlphaCleanupParams, apply_alpha_cleanup

if TYPE_CHECKING:
    from unity_ai_assets.processing.background_removal import ImageBackgroundRemover


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Outcome of optional transparency + alpha cleanup processing."""

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


class ImageProcessingPipeline:
    """Common post-processing stage after text-to-image inference."""

    def __init__(self, background_remover: ImageBackgroundRemover) -> None:
        self._background_remover = background_remover

    @property
    def background_remover(self) -> ImageBackgroundRemover:
        return self._background_remover

    def process(
        self,
        image: Image.Image,
        *,
        transparency_strategy: str,
        alpha_params: AlphaCleanupParams,
        preserve_original: bool = True,
    ) -> ProcessingResult:
        """Apply transparency strategy then deterministic alpha cleanup when needed."""
        strategy = (transparency_strategy or TransparencyStrategy.NONE.value).strip().lower()
        original = image.copy() if preserve_original else None

        if strategy == TransparencyStrategy.NONE.value:
            # Texture path: leave image as-is (typically RGB). No forced RGBA.
            return ProcessingResult(
                image=image,
                original_image=None,
                transparency_strategy=strategy,
                background_removal_applied=False,
                background_removal_implementation=None,
                alpha_cleanup_applied=False,
                alpha_threshold=alpha_params.alpha_threshold,
                alpha_feather=alpha_params.alpha_feather,
                remove_near_transparent=alpha_params.remove_near_transparent,
                zero_rgb_when_transparent=alpha_params.zero_rgb_when_transparent,
            )

        if strategy != TransparencyStrategy.BACKGROUND_REMOVAL.value:
            raise AppError(
                f"Transparency strategy '{strategy}' is not supported.",
                code=AppErrorCode.TRANSPARENCY_STRATEGY_UNSUPPORTED,
            )

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

        cleaned = apply_alpha_cleanup(rgba, alpha_params)
        return ProcessingResult(
            image=cleaned,
            original_image=original,
            transparency_strategy=strategy,
            background_removal_applied=True,
            background_removal_implementation=self._background_remover.implementation_id,
            alpha_cleanup_applied=True,
            alpha_threshold=alpha_params.alpha_threshold,
            alpha_feather=alpha_params.alpha_feather,
            remove_near_transparent=alpha_params.remove_near_transparent,
            zero_rgb_when_transparent=alpha_params.zero_rgb_when_transparent,
        )
