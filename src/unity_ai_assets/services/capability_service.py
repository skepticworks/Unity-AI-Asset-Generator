"""Capability assembly from policy, settings, and inference backends."""

from __future__ import annotations

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.version import (
    API_MAJOR_VERSION,
    API_MINOR_VERSION,
    APPLICATION_NAME,
    CAPABILITIES_SCHEMA_VERSION,
    GENERATION_MANIFEST_SCHEMA_VERSION,
)
from unity_ai_assets.domain.capabilities import (
    ApiVersionInfo,
    ApplicationIdentity,
    CapabilityDocument,
    ConcurrencyLimits,
    DimensionConstraints,
    InferenceCapabilities,
    ModelIdentity,
    NegativePromptConstraints,
    NumericRangeFloat,
    NumericRangeInt,
    OperationsCapabilities,
    OutputNameConstraints,
    PrecisionCapabilities,
    PromptConstraints,
    RuntimeState,
    SchedulerCapabilities,
    SchemaVersions,
    SeedConstraints,
    TextToImageCapabilities,
    UnsupportedOperation,
)
from unity_ai_assets.domain.enums import AssetType
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.inference.backend import ImageGenerationBackend


class CapabilityService:
    """Builds the public capability document without loading model weights."""

    def __init__(
        self,
        settings: Settings,
        policy: GenerationPolicy,
        backend: ImageGenerationBackend,
    ) -> None:
        self._settings = settings
        self._policy = policy
        self._backend = backend

    def get_capabilities(self) -> CapabilityDocument:
        """Assemble the versioned capability document."""
        inference = self._backend.describe_capabilities()
        return self._assemble(inference)

    def _assemble(self, inference: InferenceCapabilities) -> CapabilityDocument:
        policy = self._policy
        settings = self._settings

        # Prefer backend-reported scheduler default when selection is unsupported;
        # policy/settings remain the configured public identifier.
        default_scheduler = (
            inference.default_scheduler if inference.default_scheduler else policy.default_scheduler
        )
        available_schedulers = (
            list(inference.available_schedulers) if inference.scheduler_selection_supported else []
        )

        text_to_image = TextToImageCapabilities(
            supported=inference.text_to_image_supported,
            asset_types=list(inference.supported_asset_types) or [AssetType.TEXTURE.value],
            dimensions=DimensionConstraints(
                minimum_width=policy.minimum_width,
                maximum_width=policy.maximum_width,
                minimum_height=policy.minimum_height,
                maximum_height=policy.maximum_height,
                width_multiple=policy.width_multiple,
                height_multiple=policy.height_multiple,
                supported_aspect_ratios=None,
            ),
            steps=NumericRangeInt(
                minimum=policy.minimum_steps,
                maximum=policy.maximum_steps,
                default=policy.default_steps,
            ),
            guidance_scale=NumericRangeFloat(
                minimum=policy.minimum_guidance_scale,
                maximum=policy.maximum_guidance_scale,
                default=policy.default_guidance_scale,
            ),
            seed=SeedConstraints(
                minimum=policy.minimum_seed,
                maximum=policy.maximum_seed,
                random_when_omitted=policy.seed_random_when_omitted,
            ),
            prompt=PromptConstraints(maximum_length=policy.maximum_prompt_length),
            negative_prompt=NegativePromptConstraints(
                supported=policy.negative_prompt_supported,
                maximum_length=policy.maximum_negative_prompt_length,
            ),
            output_name=OutputNameConstraints(
                maximum_length=policy.maximum_output_name_length,
            ),
            schedulers=SchedulerCapabilities(
                selection_supported=inference.scheduler_selection_supported,
                default=default_scheduler,
                available=available_schedulers,
            ),
        )

        return CapabilityDocument(
            api=ApiVersionInfo(major=API_MAJOR_VERSION, minor=API_MINOR_VERSION),
            application=ApplicationIdentity(
                name=APPLICATION_NAME,
                version=settings.app_version,
            ),
            schemas=SchemaVersions(
                capabilities=CAPABILITIES_SCHEMA_VERSION,
                generation_manifest=GENERATION_MANIFEST_SCHEMA_VERSION,
            ),
            runtime=RuntimeState(
                configured_device=settings.device,
                resolved_device=inference.resolved_device,
                configured_precision=settings.torch_dtype,
                resolved_precision=inference.resolved_precision,
                model_loaded=inference.model_loaded,
            ),
            model=ModelIdentity(
                id=settings.model_id,
                revision=settings.model_revision,
                family=settings.resolved_model_family,
                display_name=settings.model_display_name,
            ),
            operations=OperationsCapabilities(
                text_to_image=text_to_image,
                image_to_image=UnsupportedOperation(supported=inference.image_to_image_supported),
                inpainting=UnsupportedOperation(supported=inference.inpainting_supported),
            ),
            precision=PrecisionCapabilities(
                configured=settings.torch_dtype,
                resolved=inference.resolved_precision,
                available=list(inference.available_precisions),
                user_selectable=inference.precision_user_selectable,
            ),
            limits=ConcurrencyLimits(
                maximum_concurrent_generations=policy.maximum_concurrent_generations,
            ),
        )
