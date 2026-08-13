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
    AlphaCleanupCapabilities,
    ApiVersionInfo,
    ApplicationIdentity,
    BackgroundRemovalCapabilities,
    CapabilityDocument,
    ConcurrencyLimits,
    DimensionConstraints,
    ImageToImageCapabilities,
    InferenceCapabilities,
    InpaintingCapabilities,
    MaskImageConstraints,
    ModelIdentity,
    NegativePromptConstraints,
    NumericRangeFloat,
    NumericRangeInt,
    OperationsCapabilities,
    OutputNameConstraints,
    PrecisionCapabilities,
    ProcessingCapabilities,
    PromptConstraints,
    RuntimeState,
    SchedulerCapabilities,
    SchemaVersions,
    SeedConstraints,
    SourceImageConstraints,
    SpriteImportCapabilities,
    TextToImageCapabilities,
    TileableProcessingCapabilities,
)
from unity_ai_assets.domain.enums import AssetType, PivotMode, TransparencyStrategy
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.domain.mask_image import (
    MASK_BLACK_MEANS,
    MASK_CONVENTION_ID,
    MASK_WHITE_MEANS,
)
from unity_ai_assets.inference.backend import ImageGenerationBackend
from unity_ai_assets.processing.background_removal import ImageBackgroundRemover
from unity_ai_assets.processing.seam_inpaint import (
    FakeSeamInpainter,
    SeamInpainter,
    UnavailableSeamInpainter,
)


class CapabilityService:
    """Builds the public capability document without loading model weights."""

    def __init__(
        self,
        settings: Settings,
        policy: GenerationPolicy,
        backend: ImageGenerationBackend,
        background_remover: ImageBackgroundRemover | None = None,
        seam_inpainter: SeamInpainter | None = None,
    ) -> None:
        self._settings = settings
        self._policy = policy
        self._backend = backend
        self._background_remover = background_remover
        self._seam_inpainter = seam_inpainter

    def get_capabilities(self) -> CapabilityDocument:
        """Assemble the versioned capability document."""
        inference = self._backend.describe_capabilities()
        return self._assemble(inference)

    def _seam_inpaint_available(self) -> bool:
        if self._seam_inpainter is None:
            return False
        if isinstance(self._seam_inpainter, UnavailableSeamInpainter):
            return False
        if isinstance(self._seam_inpainter, FakeSeamInpainter):
            return self._seam_inpainter.available
        return bool(self._settings.seam_inpaint_enabled) and self._seam_inpainter.available

    def _background_removal_available(self) -> bool:
        if self._background_remover is None:
            return False
        # Do not force-load rembg ONNX weights during capability probes.
        from unity_ai_assets.processing.background_removal import (  # noqa: PLC0415
            FakeBackgroundRemover,
            UnavailableBackgroundRemover,
            rembg_importable,
        )

        if isinstance(self._background_remover, UnavailableBackgroundRemover):
            return False
        if isinstance(self._background_remover, FakeBackgroundRemover):
            return True
        if not self._settings.background_removal_enabled:
            return False
        # For rembg: importability without weight load is enough for advertising.
        backend = (self._settings.background_removal_backend or "").strip().lower()
        if backend in {"rembg", "rembg-u2net", ""}:
            return rembg_importable()
        return True

    def _background_removal_unavailable_reason(self) -> str | None:
        if self._background_removal_available():
            return None
        from unity_ai_assets.processing.background_removal import (  # noqa: PLC0415
            background_removal_unavailable_reason,
        )

        return background_removal_unavailable_reason(
            enabled=self._settings.background_removal_enabled,
            backend=self._settings.background_removal_backend,
            remover=self._background_remover,
        )

    def _assemble(self, inference: InferenceCapabilities) -> CapabilityDocument:
        policy = self._policy
        settings = self._settings

        default_scheduler = (
            inference.default_scheduler if inference.default_scheduler else policy.default_scheduler
        )
        available_schedulers = (
            list(inference.available_schedulers) if inference.scheduler_selection_supported else []
        )

        bg_available = self._background_removal_available()
        bg_reason = self._background_removal_unavailable_reason()
        strategies = [TransparencyStrategy.NONE.value]
        if bg_available or settings.background_removal_enabled:
            # Advertise background_removal when enabled in config even if the
            # optional dependency is missing, so Unity can show a clear reason
            # once generation is attempted / availability is probed.
            strategies.append(TransparencyStrategy.BACKGROUND_REMOVAL.value)

        remover_id = None
        remover_model = None
        if self._background_remover is not None:
            from unity_ai_assets.processing.background_removal import (  # noqa: PLC0415
                UnavailableBackgroundRemover,
            )

            if not isinstance(self._background_remover, UnavailableBackgroundRemover):
                remover_id = settings.background_removal_backend
                remover_model = settings.background_removal_model

        processing = ProcessingCapabilities(
            transparency_strategies=strategies,
            background_removal=BackgroundRemovalCapabilities(
                available=bg_available,
                backend=remover_id if settings.background_removal_enabled else None,
                model=remover_model if settings.background_removal_enabled else None,
                produces_native_alpha=False,
                unavailable_reason=None if bg_available else bg_reason,
            ),
            alpha_cleanup=AlphaCleanupCapabilities(
                available=True,
                alpha_threshold=NumericRangeInt(
                    minimum=settings.min_alpha_threshold,
                    maximum=settings.max_alpha_threshold,
                    default=settings.default_alpha_threshold,
                ),
                alpha_feather=NumericRangeInt(
                    minimum=settings.min_alpha_feather,
                    maximum=settings.max_alpha_feather,
                    default=settings.default_alpha_feather,
                ),
                remove_near_transparent_default=settings.default_remove_near_transparent,
                zero_rgb_when_transparent_default=settings.default_zero_rgb_when_transparent,
            ),
            sprite_import=SpriteImportCapabilities(
                supported=True,
                single_sprite_only=True,
                pivot_modes=[mode.value for mode in PivotMode],
            ),
            tileable=TileableProcessingCapabilities(
                available=True,
                seam_analysis=True,
                seam_correction=True,
                palette_reduction=True,
                ai_inpaint_available=self._seam_inpaint_available(),
                seam_blend_width=NumericRangeInt(
                    minimum=8,
                    maximum=128,
                    default=settings.default_seam_width,
                ),
                palette_color_count=NumericRangeInt(minimum=2, maximum=256, default=16),
                target_size=512,
                circular_offset_px=256,
                protected_border_px=4,
            ),
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
            processing=processing,
        )

        image_to_image = ImageToImageCapabilities(
            supported=inference.image_to_image_supported,
            asset_types=list(text_to_image.asset_types),
            dimensions=text_to_image.dimensions,
            steps=text_to_image.steps,
            guidance_scale=text_to_image.guidance_scale,
            seed=text_to_image.seed,
            prompt=text_to_image.prompt,
            negative_prompt=text_to_image.negative_prompt,
            output_name=text_to_image.output_name,
            schedulers=text_to_image.schedulers,
            denoising_strength=NumericRangeFloat(
                minimum=policy.minimum_denoising_strength,
                maximum=policy.maximum_denoising_strength,
                default=policy.default_denoising_strength,
            ),
            source_image=SourceImageConstraints(
                supported_formats=list(policy.supported_source_image_formats),
                maximum_byte_size=policy.maximum_source_image_bytes,
                dimensions=text_to_image.dimensions,
            ),
            processing=processing,
        )

        inpainting = InpaintingCapabilities(
            supported=inference.inpainting_supported,
            asset_types=list(text_to_image.asset_types),
            dimensions=text_to_image.dimensions,
            steps=text_to_image.steps,
            guidance_scale=text_to_image.guidance_scale,
            seed=text_to_image.seed,
            prompt=text_to_image.prompt,
            negative_prompt=text_to_image.negative_prompt,
            output_name=text_to_image.output_name,
            schedulers=text_to_image.schedulers,
            denoising_strength=NumericRangeFloat(
                minimum=policy.minimum_denoising_strength,
                maximum=policy.maximum_denoising_strength,
                default=policy.default_denoising_strength,
            ),
            source_image=SourceImageConstraints(
                supported_formats=list(policy.supported_source_image_formats),
                maximum_byte_size=policy.maximum_source_image_bytes,
                dimensions=text_to_image.dimensions,
            ),
            mask_image=MaskImageConstraints(
                supported_formats=list(policy.supported_mask_image_formats),
                maximum_byte_size=policy.maximum_mask_image_bytes,
                dimensions=text_to_image.dimensions,
                must_match_source_dimensions=True,
                convention=MASK_CONVENTION_ID,
                white_means=MASK_WHITE_MEANS,
                black_means=MASK_BLACK_MEANS,
                alpha_ignored=True,
            ),
            processing=processing,
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
                image_to_image=image_to_image,
                inpainting=inpainting,
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
