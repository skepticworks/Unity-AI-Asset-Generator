"""Image post-processing (transparency, tileable seam/palette) for generated assets."""

from unity_ai_assets.processing.alpha_cleanup import AlphaCleanupParams, apply_alpha_cleanup
from unity_ai_assets.processing.background_removal import (
    FakeBackgroundRemover,
    ImageBackgroundRemover,
    create_background_remover,
)
from unity_ai_assets.processing.offset_wrap import circular_shift, offset_preview, tiled_preview
from unity_ai_assets.processing.palette import PaletteReductionParams, reduce_palette
from unity_ai_assets.processing.pipeline import ImageProcessingPipeline, ProcessingResult
from unity_ai_assets.processing.seam_analysis import SeamAnalysisResult, analyze_seams
from unity_ai_assets.processing.seam_correction import SeamCorrectionParams, correct_seams
from unity_ai_assets.processing.seam_inpaint import (
    FakeSeamInpainter,
    SeamInpainter,
    UnavailableSeamInpainter,
    create_seam_inpainter,
)
from unity_ai_assets.processing.seamless_repair import (
    SeamlessRepairParams,
    make_seamless_with_inpaint,
)
from unity_ai_assets.processing.tileable import (
    TileableProcessingParams,
    TileableProcessingResult,
    apply_tileable_processing,
)
from unity_ai_assets.processing.wrap_diagnostics import (
    WrapDiscontinuityResult,
    analyze_wrap_discontinuity,
)

__all__ = [
    "AlphaCleanupParams",
    "FakeBackgroundRemover",
    "FakeSeamInpainter",
    "ImageBackgroundRemover",
    "ImageProcessingPipeline",
    "PaletteReductionParams",
    "ProcessingResult",
    "SeamAnalysisResult",
    "SeamCorrectionParams",
    "SeamInpainter",
    "SeamlessRepairParams",
    "TileableProcessingParams",
    "TileableProcessingResult",
    "UnavailableSeamInpainter",
    "WrapDiscontinuityResult",
    "analyze_seams",
    "analyze_wrap_discontinuity",
    "apply_alpha_cleanup",
    "apply_tileable_processing",
    "circular_shift",
    "correct_seams",
    "create_background_remover",
    "create_seam_inpainter",
    "make_seamless_with_inpaint",
    "offset_preview",
    "reduce_palette",
    "tiled_preview",
]
