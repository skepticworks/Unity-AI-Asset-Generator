"""Pydantic schemas for the versioned capability document."""

from __future__ import annotations

from pydantic import BaseModel, Field

from unity_ai_assets.domain.capabilities import CapabilityDocument


class ApiVersionSchema(BaseModel):
    """API major/minor version."""

    major: int = Field(description="API major version; incompatible when mismatched")
    minor: int = Field(description="API minor version; newer minors may be compatible")


class ApplicationSchema(BaseModel):
    """Application identity."""

    name: str = Field(description="Application name")
    version: str = Field(description="Application semantic version")


class SchemasSchema(BaseModel):
    """Independent schema versions."""

    capabilities: str = Field(description="Capability document schema version")
    generation_manifest: str = Field(description="Generation manifest schema version")


class RuntimeSchema(BaseModel):
    """Configured versus resolved runtime state."""

    configured_device: str = Field(description="Configured device preference")
    resolved_device: str = Field(description="Device currently resolved for inference")
    configured_precision: str = Field(description="Configured precision preference")
    resolved_precision: str = Field(description="Precision currently resolved for inference")
    model_loaded: bool = Field(description="Whether model weights are currently loaded")


class ModelSchema(BaseModel):
    """Configured model identity (no weight loading required)."""

    id: str = Field(description="Configured model identifier")
    revision: str | None = Field(description="Configured model revision, if any")
    family: str = Field(description="Model family (e.g. sd15, sdxl, unknown)")
    display_name: str | None = Field(description="Optional human-readable model name")


class DimensionConstraintsSchema(BaseModel):
    """Width/height constraints."""

    minimum_width: int
    maximum_width: int
    minimum_height: int
    maximum_height: int
    width_multiple: int
    height_multiple: int
    supported_aspect_ratios: list[str] | None = None


class IntRangeSchema(BaseModel):
    """Integer range with default."""

    minimum: int
    maximum: int
    default: int


class FloatRangeSchema(BaseModel):
    """Float range with default."""

    minimum: float
    maximum: float
    default: float


class SeedConstraintsSchema(BaseModel):
    """Seed bounds."""

    minimum: int
    maximum: int
    random_when_omitted: bool


class PromptConstraintsSchema(BaseModel):
    """Prompt constraints."""

    maximum_length: int


class NegativePromptConstraintsSchema(BaseModel):
    """Negative prompt constraints."""

    supported: bool
    maximum_length: int


class OutputNameConstraintsSchema(BaseModel):
    """Output name constraints."""

    maximum_length: int


class SchedulerCapabilitiesSchema(BaseModel):
    """Scheduler selection behavior."""

    selection_supported: bool
    default: str
    available: list[str] = Field(default_factory=list)


class BackgroundRemovalCapabilitiesSchema(BaseModel):
    """Local background-removal availability (post-processing, not native alpha)."""

    available: bool
    backend: str | None = None
    model: str | None = None
    produces_native_alpha: bool = False
    unavailable_reason: str | None = None


class AlphaCleanupCapabilitiesSchema(BaseModel):
    """Deterministic alpha cleanup ranges."""

    available: bool
    alpha_threshold: IntRangeSchema
    alpha_feather: IntRangeSchema
    remove_near_transparent_default: bool
    zero_rgb_when_transparent_default: bool


class SpriteImportCapabilitiesSchema(BaseModel):
    """Sprite import support advertised for Unity clients."""

    supported: bool
    single_sprite_only: bool = True
    pivot_modes: list[str] = Field(default_factory=list)


class TileableProcessingCapabilitiesSchema(BaseModel):
    """Tileable texture workflow capabilities."""

    available: bool = True
    seam_analysis: bool = True
    seam_correction: bool = True
    palette_reduction: bool = True
    ai_inpaint_available: bool = False
    seam_blend_width: IntRangeSchema
    palette_color_count: IntRangeSchema
    target_size: int = 512
    circular_offset_px: int = 256
    protected_border_px: int = 4


class ProcessingCapabilitiesSchema(BaseModel):
    """Post-inference processing capabilities."""

    transparency_strategies: list[str]
    background_removal: BackgroundRemovalCapabilitiesSchema
    alpha_cleanup: AlphaCleanupCapabilitiesSchema
    sprite_import: SpriteImportCapabilitiesSchema
    tileable: TileableProcessingCapabilitiesSchema | None = None


class TextToImageCapabilitiesSchema(BaseModel):
    """Text-to-image operation capabilities."""

    supported: bool
    asset_types: list[str]
    dimensions: DimensionConstraintsSchema
    steps: IntRangeSchema
    guidance_scale: FloatRangeSchema
    seed: SeedConstraintsSchema
    prompt: PromptConstraintsSchema
    negative_prompt: NegativePromptConstraintsSchema
    output_name: OutputNameConstraintsSchema
    schedulers: SchedulerCapabilitiesSchema
    processing: ProcessingCapabilitiesSchema | None = None


class UnsupportedOperationSchema(BaseModel):
    """Unsupported operation marker."""

    supported: bool = False


class OperationsSchema(BaseModel):
    """Per-operation capabilities."""

    text_to_image: TextToImageCapabilitiesSchema
    image_to_image: UnsupportedOperationSchema
    inpainting: UnsupportedOperationSchema


class PrecisionSchema(BaseModel):
    """Precision reporting."""

    configured: str
    resolved: str
    available: list[str]
    user_selectable: bool


class LimitsSchema(BaseModel):
    """Concurrency and related limits."""

    maximum_concurrent_generations: int


class CapabilitiesResponse(BaseModel):
    """Versioned public capability document."""

    api: ApiVersionSchema
    application: ApplicationSchema
    schemas: SchemasSchema
    runtime: RuntimeSchema
    model: ModelSchema
    operations: OperationsSchema
    precision: PrecisionSchema
    limits: LimitsSchema

    @classmethod
    def from_domain(cls, document: CapabilityDocument) -> CapabilitiesResponse:
        """Map a domain capability document to the public response schema."""
        t2i = document.operations.text_to_image
        processing_schema: ProcessingCapabilitiesSchema | None = None
        if t2i.processing is not None:
            proc = t2i.processing
            processing_schema = ProcessingCapabilitiesSchema(
                transparency_strategies=list(proc.transparency_strategies),
                background_removal=BackgroundRemovalCapabilitiesSchema(
                    available=proc.background_removal.available,
                    backend=proc.background_removal.backend,
                    model=proc.background_removal.model,
                    produces_native_alpha=proc.background_removal.produces_native_alpha,
                    unavailable_reason=proc.background_removal.unavailable_reason,
                ),
                alpha_cleanup=AlphaCleanupCapabilitiesSchema(
                    available=proc.alpha_cleanup.available,
                    alpha_threshold=IntRangeSchema(
                        minimum=proc.alpha_cleanup.alpha_threshold.minimum,
                        maximum=proc.alpha_cleanup.alpha_threshold.maximum,
                        default=proc.alpha_cleanup.alpha_threshold.default
                        or proc.alpha_cleanup.alpha_threshold.minimum,
                    ),
                    alpha_feather=IntRangeSchema(
                        minimum=proc.alpha_cleanup.alpha_feather.minimum,
                        maximum=proc.alpha_cleanup.alpha_feather.maximum,
                        default=proc.alpha_cleanup.alpha_feather.default
                        or proc.alpha_cleanup.alpha_feather.minimum,
                    ),
                    remove_near_transparent_default=(
                        proc.alpha_cleanup.remove_near_transparent_default
                    ),
                    zero_rgb_when_transparent_default=(
                        proc.alpha_cleanup.zero_rgb_when_transparent_default
                    ),
                ),
                sprite_import=SpriteImportCapabilitiesSchema(
                    supported=proc.sprite_import.supported,
                    single_sprite_only=proc.sprite_import.single_sprite_only,
                    pivot_modes=list(proc.sprite_import.pivot_modes),
                ),
                tileable=(
                    None
                    if proc.tileable is None
                    else TileableProcessingCapabilitiesSchema(
                        available=proc.tileable.available,
                        seam_analysis=proc.tileable.seam_analysis,
                        seam_correction=proc.tileable.seam_correction,
                        palette_reduction=proc.tileable.palette_reduction,
                        ai_inpaint_available=proc.tileable.ai_inpaint_available,
                        seam_blend_width=IntRangeSchema(
                            minimum=proc.tileable.seam_blend_width.minimum,
                            maximum=proc.tileable.seam_blend_width.maximum,
                            default=proc.tileable.seam_blend_width.default
                            or proc.tileable.seam_blend_width.minimum,
                        ),
                        palette_color_count=IntRangeSchema(
                            minimum=proc.tileable.palette_color_count.minimum,
                            maximum=proc.tileable.palette_color_count.maximum,
                            default=proc.tileable.palette_color_count.default
                            or proc.tileable.palette_color_count.minimum,
                        ),
                        target_size=proc.tileable.target_size,
                        circular_offset_px=proc.tileable.circular_offset_px,
                        protected_border_px=proc.tileable.protected_border_px,
                    )
                ),
            )
        return cls(
            api=ApiVersionSchema(major=document.api.major, minor=document.api.minor),
            application=ApplicationSchema(
                name=document.application.name,
                version=document.application.version,
            ),
            schemas=SchemasSchema(
                capabilities=document.schemas.capabilities,
                generation_manifest=document.schemas.generation_manifest,
            ),
            runtime=RuntimeSchema(
                configured_device=document.runtime.configured_device,
                resolved_device=document.runtime.resolved_device,
                configured_precision=document.runtime.configured_precision,
                resolved_precision=document.runtime.resolved_precision,
                model_loaded=document.runtime.model_loaded,
            ),
            model=ModelSchema(
                id=document.model.id,
                revision=document.model.revision,
                family=document.model.family,
                display_name=document.model.display_name,
            ),
            operations=OperationsSchema(
                text_to_image=TextToImageCapabilitiesSchema(
                    supported=t2i.supported,
                    asset_types=list(t2i.asset_types),
                    dimensions=DimensionConstraintsSchema(
                        minimum_width=t2i.dimensions.minimum_width,
                        maximum_width=t2i.dimensions.maximum_width,
                        minimum_height=t2i.dimensions.minimum_height,
                        maximum_height=t2i.dimensions.maximum_height,
                        width_multiple=t2i.dimensions.width_multiple,
                        height_multiple=t2i.dimensions.height_multiple,
                        supported_aspect_ratios=t2i.dimensions.supported_aspect_ratios,
                    ),
                    steps=IntRangeSchema(
                        minimum=t2i.steps.minimum,
                        maximum=t2i.steps.maximum,
                        default=t2i.steps.default or t2i.steps.minimum,
                    ),
                    guidance_scale=FloatRangeSchema(
                        minimum=t2i.guidance_scale.minimum,
                        maximum=t2i.guidance_scale.maximum,
                        default=t2i.guidance_scale.default
                        if t2i.guidance_scale.default is not None
                        else t2i.guidance_scale.minimum,
                    ),
                    seed=SeedConstraintsSchema(
                        minimum=t2i.seed.minimum,
                        maximum=t2i.seed.maximum,
                        random_when_omitted=t2i.seed.random_when_omitted,
                    ),
                    prompt=PromptConstraintsSchema(
                        maximum_length=t2i.prompt.maximum_length,
                    ),
                    negative_prompt=NegativePromptConstraintsSchema(
                        supported=t2i.negative_prompt.supported,
                        maximum_length=t2i.negative_prompt.maximum_length,
                    ),
                    output_name=OutputNameConstraintsSchema(
                        maximum_length=t2i.output_name.maximum_length,
                    ),
                    schedulers=SchedulerCapabilitiesSchema(
                        selection_supported=t2i.schedulers.selection_supported,
                        default=t2i.schedulers.default,
                        available=list(t2i.schedulers.available),
                    ),
                    processing=processing_schema,
                ),
                image_to_image=UnsupportedOperationSchema(
                    supported=document.operations.image_to_image.supported,
                ),
                inpainting=UnsupportedOperationSchema(
                    supported=document.operations.inpainting.supported,
                ),
            ),
            precision=PrecisionSchema(
                configured=document.precision.configured,
                resolved=document.precision.resolved,
                available=list(document.precision.available),
                user_selectable=document.precision.user_selectable,
            ),
            limits=LimitsSchema(
                maximum_concurrent_generations=document.limits.maximum_concurrent_generations,
            ),
        )
