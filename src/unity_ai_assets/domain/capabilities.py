"""Domain models for versioned capability reporting."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ApiVersionInfo:
    """Public API major/minor version."""

    major: int
    minor: int


@dataclass(frozen=True, slots=True)
class ApplicationIdentity:
    """Application name and semantic version."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class SchemaVersions:
    """Independent schema versions exposed to clients."""

    capabilities: str
    generation_manifest: str


@dataclass(frozen=True, slots=True)
class RuntimeState:
    """Configured versus resolved runtime device/precision and load state."""

    configured_device: str
    resolved_device: str
    configured_precision: str
    resolved_precision: str
    model_loaded: bool


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Configured model identity without requiring weight loading."""

    id: str
    revision: str | None
    family: str
    display_name: str | None


@dataclass(frozen=True, slots=True)
class DimensionConstraints:
    """Width/height limits and multiples for an operation."""

    minimum_width: int
    maximum_width: int
    minimum_height: int
    maximum_height: int
    width_multiple: int
    height_multiple: int
    supported_aspect_ratios: list[str] | None = None


@dataclass(frozen=True, slots=True)
class NumericRangeInt:
    """Integer parameter range with optional default."""

    minimum: int
    maximum: int
    default: int | None = None


@dataclass(frozen=True, slots=True)
class NumericRangeFloat:
    """Float parameter range with optional default."""

    minimum: float
    maximum: float
    default: float | None = None


@dataclass(frozen=True, slots=True)
class SeedConstraints:
    """Seed bounds and random-when-omitted behavior."""

    minimum: int
    maximum: int
    random_when_omitted: bool


@dataclass(frozen=True, slots=True)
class PromptConstraints:
    """Prompt length limit."""

    maximum_length: int


@dataclass(frozen=True, slots=True)
class NegativePromptConstraints:
    """Negative-prompt support and length limit."""

    supported: bool
    maximum_length: int


@dataclass(frozen=True, slots=True)
class OutputNameConstraints:
    """Output basename length limit."""

    maximum_length: int


@dataclass(frozen=True, slots=True)
class SchedulerCapabilities:
    """Scheduler selection behavior and public identifiers."""

    selection_supported: bool
    default: str
    available: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BackgroundRemovalCapabilities:
    """Whether local background-removal post-processing is available."""

    available: bool
    backend: str | None = None
    model: str | None = None
    produces_native_alpha: bool = False
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AlphaCleanupCapabilities:
    """Deterministic alpha cleanup support and parameter ranges."""

    available: bool
    alpha_threshold: NumericRangeInt
    alpha_feather: NumericRangeInt
    remove_near_transparent_default: bool
    zero_rgb_when_transparent_default: bool


@dataclass(frozen=True, slots=True)
class SpriteImportCapabilities:
    """Whether Unity-oriented sprite import settings are supported in-product."""

    supported: bool
    single_sprite_only: bool = True
    pivot_modes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TileableProcessingCapabilities:
    """Tileable texture workflow support advertised to clients."""

    available: bool = True
    seam_analysis: bool = True
    seam_correction: bool = True
    palette_reduction: bool = True
    ai_inpaint_available: bool = False
    seam_blend_width: NumericRangeInt = field(
        default_factory=lambda: NumericRangeInt(minimum=8, maximum=128, default=64)
    )
    palette_color_count: NumericRangeInt = field(
        default_factory=lambda: NumericRangeInt(minimum=2, maximum=256, default=16)
    )
    target_size: int = 512
    circular_offset_px: int = 256
    protected_border_px: int = 4


@dataclass(frozen=True, slots=True)
class ProcessingCapabilities:
    """Post-inference processing capabilities (transparency, alpha cleanup, tileable).

    Transparency produced via post-processing is reported separately from
    image generation so clients do not assume the diffusion model emits alpha.
    """

    transparency_strategies: list[str]
    background_removal: BackgroundRemovalCapabilities
    alpha_cleanup: AlphaCleanupCapabilities
    sprite_import: SpriteImportCapabilities
    tileable: TileableProcessingCapabilities | None = None


@dataclass(frozen=True, slots=True)
class TextToImageCapabilities:
    """Constraints for the text-to-image operation."""

    supported: bool
    asset_types: list[str]
    dimensions: DimensionConstraints
    steps: NumericRangeInt
    guidance_scale: NumericRangeFloat
    seed: SeedConstraints
    prompt: PromptConstraints
    negative_prompt: NegativePromptConstraints
    output_name: OutputNameConstraints
    schedulers: SchedulerCapabilities
    processing: ProcessingCapabilities | None = None


@dataclass(frozen=True, slots=True)
class SourceImageConstraints:
    """Constraints for the img2img init/source image (not reference conditioning)."""

    supported_formats: list[str]
    maximum_byte_size: int
    dimensions: DimensionConstraints | None = None


@dataclass(frozen=True, slots=True)
class MaskImageConstraints:
    """Constraints and explicit semantics for an inpainting mask."""

    supported_formats: list[str]
    maximum_byte_size: int
    dimensions: DimensionConstraints | None = None
    must_match_source_dimensions: bool = True
    convention: str = "white_inpaints"
    white_means: str = "regenerate"
    black_means: str = "keep"
    alpha_ignored: bool = True


@dataclass(frozen=True, slots=True)
class ImageToImageCapabilities:
    """Constraints for image-to-image (init-image) generation.

    The source image is the generation latent starting point and is modified
    according to denoising strength. This is not reference-image conditioning.
    """

    supported: bool
    asset_types: list[str]
    dimensions: DimensionConstraints
    steps: NumericRangeInt
    guidance_scale: NumericRangeFloat
    seed: SeedConstraints
    prompt: PromptConstraints
    negative_prompt: NegativePromptConstraints
    output_name: OutputNameConstraints
    schedulers: SchedulerCapabilities
    denoising_strength: NumericRangeFloat
    source_image: SourceImageConstraints
    processing: ProcessingCapabilities | None = None


@dataclass(frozen=True, slots=True)
class UnsupportedOperation:
    """Minimal declaration for an unimplemented operation."""

    supported: bool = False


@dataclass(frozen=True, slots=True)
class InpaintingCapabilities:
    """Constraints for masked inpainting (distinct from img2img and IP-Adapter).

    White mask pixels are regenerated; black pixels are kept from the source.
    """

    supported: bool
    asset_types: list[str]
    dimensions: DimensionConstraints
    steps: NumericRangeInt
    guidance_scale: NumericRangeFloat
    seed: SeedConstraints
    prompt: PromptConstraints
    negative_prompt: NegativePromptConstraints
    output_name: OutputNameConstraints
    schedulers: SchedulerCapabilities
    denoising_strength: NumericRangeFloat
    source_image: SourceImageConstraints
    mask_image: MaskImageConstraints
    processing: ProcessingCapabilities | None = None


@dataclass(frozen=True, slots=True)
class OperationsCapabilities:
    """Per-operation capability declarations."""

    text_to_image: TextToImageCapabilities
    image_to_image: ImageToImageCapabilities
    inpainting: InpaintingCapabilities


@dataclass(frozen=True, slots=True)
class PrecisionCapabilities:
    """Process-level precision reporting."""

    configured: str
    resolved: str
    available: list[str]
    user_selectable: bool


@dataclass(frozen=True, slots=True)
class ConcurrencyLimits:
    """Concurrency limits exposed to clients."""

    maximum_concurrent_generations: int


@dataclass(frozen=True, slots=True)
class JobSystemCapabilities:
    """Local job queue advertised to clients. Execution backend is not exposed."""

    supported: bool = True
    persistence: str = "local_filesystem"
    states: list[str] = field(
        default_factory=lambda: [
            "queued",
            "running",
            "completed",
            "failed",
            "cancelling",
            "cancelled",
            "interrupted",
        ]
    )
    maximum_retries: int = 2
    maximum_concurrent_jobs: int = 1
    auto_retry: bool = True
    progress: str = "stage"


@dataclass(frozen=True, slots=True)
class BatchGenerationCapabilities:
    """Batch orchestration over the local job queue. Not a second executor."""

    supported: bool = True
    maximum_jobs: int = 32
    maximum_prompts: int = 50
    maximum_variations: int = 16
    seed_modes: list[str] = field(
        default_factory=lambda: ["fixed", "random", "sequential"]
    )
    states: list[str] = field(
        default_factory=lambda: [
            "queued",
            "running",
            "cancelling",
            "completed",
            "partial_success",
            "failed",
            "cancelled",
        ]
    )


@dataclass(frozen=True, slots=True)
class CapabilityDocument:
    """Complete versioned capability document (domain form)."""

    api: ApiVersionInfo
    application: ApplicationIdentity
    schemas: SchemaVersions
    runtime: RuntimeState
    model: ModelIdentity
    operations: OperationsCapabilities
    precision: PrecisionCapabilities
    limits: ConcurrencyLimits
    jobs: JobSystemCapabilities = field(default_factory=JobSystemCapabilities)
    batches: BatchGenerationCapabilities = field(default_factory=BatchGenerationCapabilities)


@dataclass(frozen=True, slots=True)
class InferenceCapabilities:
    """Capability fragment contributed by an inference backend.

    Must not require loading model weights. Public identifiers only —
    never Diffusers class names.
    """

    text_to_image_supported: bool
    image_to_image_supported: bool
    inpainting_supported: bool
    supported_asset_types: list[str]
    scheduler_selection_supported: bool
    default_scheduler: str
    available_schedulers: list[str]
    available_precisions: list[str]
    precision_user_selectable: bool
    model_loaded: bool
    resolved_device: str
    resolved_precision: str
