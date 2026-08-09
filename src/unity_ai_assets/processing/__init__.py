"""Image post-processing (background removal, alpha cleanup) for sprites/icons."""

from unity_ai_assets.processing.alpha_cleanup import AlphaCleanupParams, apply_alpha_cleanup
from unity_ai_assets.processing.background_removal import (
    FakeBackgroundRemover,
    ImageBackgroundRemover,
    create_background_remover,
)
from unity_ai_assets.processing.pipeline import ImageProcessingPipeline, ProcessingResult

__all__ = [
    "AlphaCleanupParams",
    "FakeBackgroundRemover",
    "ImageBackgroundRemover",
    "ImageProcessingPipeline",
    "ProcessingResult",
    "apply_alpha_cleanup",
    "create_background_remover",
]
