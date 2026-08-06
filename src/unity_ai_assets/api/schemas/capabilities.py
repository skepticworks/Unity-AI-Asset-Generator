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
