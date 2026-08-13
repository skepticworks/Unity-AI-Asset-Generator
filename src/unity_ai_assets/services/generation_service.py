"""Orchestrates validation, inference, post-processing, and persistence."""

from __future__ import annotations

import contextvars
import inspect
import math
import re
import secrets
import threading
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import (
    AssetTypeUnsupportedError,
    BackgroundRemovalUnavailableError,
    FieldIssue,
    GenerationCancelledError,
    GenerationRequestInvalidError,
    OperationUnsupportedError,
    PivotInvalidError,
    PixelsPerUnitInvalidError,
    SeamInpaintUnavailableError,
    TransparencyStrategyUnsupportedError,
)
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.core.request_context import get_request_id
from unity_ai_assets.domain.enums import (
    AssetType,
    OperationType,
    PivotMode,
    TransparencyStrategy,
    is_known_pivot_mode,
    is_known_transparency_strategy,
)
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest, GenerationResult
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.domain.mask_image import (
    MASK_CONVENTION_ID,
    assert_source_mask_dimensions_match,
    decode_mask_image_base64,
    prepare_inpaint_mask,
    prepare_inpaint_source,
    validate_mask_image,
)
from unity_ai_assets.domain.source_image import (
    decode_source_image_base64,
    prepare_init_image,
    validate_source_image,
)
from unity_ai_assets.processing.alpha_cleanup import AlphaCleanupParams
from unity_ai_assets.processing.pipeline import ImageProcessingPipeline, ProcessingResult
from unity_ai_assets.processing.tileable import TileableProcessingParams
from unity_ai_assets.services.output_service import OutputService, sanitize_output_name

if TYPE_CHECKING:
    from unity_ai_assets.inference.backend import ImageGenerationBackend

logger = get_logger(__name__)
_PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_ATLAS_HINT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SPRITE_ICON_TYPES = frozenset({AssetType.SPRITE.value, AssetType.ICON.value})
ProgressHook = Callable[[str, int | None, int | None], None]
_validation_only: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "generation_validation_only", default=False
)


class _ValidatedRequestError(Exception):
    """Internal signal used to return a resolved seed without running inference."""

    def __init__(self, seed: int) -> None:
        super().__init__("validated")
        self.seed = seed


def raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    """Raise GenerationCancelledError when a job cancel event is set."""
    if cancel_event is not None and cancel_event.is_set():
        raise GenerationCancelledError("Generation cancelled at a safe interruption point.")


def _validate_provenance(
    *,
    identifiers: dict[str, str | None],
    revisions: dict[str, int | None],
    profile_origin: str | None,
) -> None:
    issues: dict[str, list[FieldIssue]] = {}
    for field, value in identifiers.items():
        if value is not None and _PROFILE_ID_PATTERN.fullmatch(value) is None:
            issues[field] = [
                FieldIssue(
                    code=FieldIssueCode.FORMAT_INVALID,
                    message=(
                        "Profile identifiers must be at most 128 characters and contain "
                        "only letters, digits, underscores, or hyphens."
                    ),
                    actual=value,
                )
            ]
    for field, revision_value in revisions.items():
        if revision_value is not None and revision_value < 1:
            issues[field] = [
                FieldIssue(
                    code=FieldIssueCode.VALUE_INVALID,
                    message="Profile revisions must be positive integers.",
                    actual=revision_value,
                )
            ]
    if profile_origin is not None and profile_origin not in {"builtin", "user", "none"}:
        issues["profile_origin"] = [
            FieldIssue(
                code=FieldIssueCode.VALUE_INVALID,
                message="profile_origin must be builtin, user, or none.",
                actual=profile_origin,
            )
        ]
    if issues:
        raise GenerationRequestInvalidError("Invalid profile provenance.", field_issues=issues)


class GenerationService:
    """Coordinates a single text-to-image generation request."""

    def __init__(
        self,
        backend: ImageGenerationBackend,
        output_service: OutputService,
        settings: Settings,
        policy: GenerationPolicy | None = None,
        processing_pipeline: ImageProcessingPipeline | None = None,
    ) -> None:
        self._backend = backend
        self._output_service = output_service
        self._settings = settings
        self._policy = policy or GenerationPolicy.from_settings(settings)
        self._processing = processing_pipeline
        self._generation_lock = threading.Lock()

    @property
    def backend(self) -> ImageGenerationBackend:
        return self._backend

    @property
    def policy(self) -> GenerationPolicy:
        return self._policy

    @property
    def exclusive_model_vram(self) -> bool:
        """True when only one diffusion pipeline should occupy VRAM at a time."""
        return bool(self._settings.exclusive_model_vram) and not bool(
            self._settings.enable_cpu_offload
        )

    def validate_texture_request(self, **kwargs: Any) -> int:
        """Validate generation parameters and return the resolved seed.

        Does not acquire the GPU lock or persist outputs. Deterministic
        validation failures raise the same AppError types as generate_texture.
        """
        kwargs.pop("cancel_event", None)
        kwargs.pop("on_progress", None)
        token = _validation_only.set(True)
        try:
            self.generate_texture(**kwargs)
        except _ValidatedRequestError as validated:
            return validated.seed
        finally:
            _validation_only.reset(token)
        raise RuntimeError("Generation validation did not resolve a seed.")

    @staticmethod
    def _report_progress(
        on_progress: ProgressHook | None,
        stage: str,
        *,
        current_step: int | None = None,
        total_steps: int | None = None,
    ) -> None:
        if on_progress is not None:
            on_progress(stage, current_step, total_steps)

    def _unload_txt2img(self, *, reason: str) -> None:
        unload = getattr(self._backend, "unload_weights", None)
        if not callable(unload):
            return
        if unload():
            logger.info("Freed txt2img VRAM (%s)", reason)

    def _unload_inpaint(self, *, reason: str) -> None:
        if self._processing is None:
            return
        unload = getattr(self._processing.seam_inpainter, "unload_weights", None)
        if not callable(unload):
            return
        if unload():
            logger.info("Freed seam-inpaint VRAM (%s)", reason)

    def _unload_background_removal(self, *, reason: str) -> None:
        if self._processing is None:
            return
        unload = getattr(self._processing.background_remover, "unload_weights", None)
        if not callable(unload):
            return
        if unload():
            logger.info("Freed background-removal VRAM (%s)", reason)

    def generate_texture(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int | None = None,
        guidance_scale: float | None = None,
        seed: int | None = None,
        output_name: str = "texture",
        generation_profile_id: str | None = None,
        generation_profile_revision: int | None = None,
        profile_origin: str | None = None,
        prompt_template_id: str | None = None,
        prompt_template_revision: int | None = None,
        negative_prompt_profile_id: str | None = None,
        negative_prompt_profile_revision: int | None = None,
        unity_import_profile_id: str | None = None,
        asset_type: str = "texture",
        transparency_strategy: str | None = None,
        alpha_threshold: int | None = None,
        alpha_feather: int | None = None,
        remove_near_transparent: bool | None = None,
        zero_rgb_when_transparent: bool | None = None,
        pixels_per_unit: float | None = None,
        pivot_mode: str | None = None,
        custom_pivot_x: float | None = None,
        custom_pivot_y: float | None = None,
        atlas_hint: str | None = None,
        tileable: bool | None = None,
        apply_seam_correction: bool | None = None,
        seam_blend_width: int | None = None,
        palette_reduction_enabled: bool | None = None,
        palette_color_count: int | None = None,
        operation: str | None = None,
        source_image_base64: str | None = None,
        source_image_media_type: str | None = None,
        mask_image_base64: str | None = None,
        mask_image_media_type: str | None = None,
        denoising_strength: float | None = None,
        cancel_event: threading.Event | None = None,
        on_progress: ProgressHook | None = None,
    ) -> GenerationResult:
        """Validate inputs against policy, run inference under a lock, and persist."""
        raise_if_cancelled(cancel_event)
        self._report_progress(on_progress, "validating")
        policy = self._policy
        settings = self._settings
        resolved_steps = policy.default_steps if steps is None else steps
        resolved_guidance = (
            policy.default_guidance_scale if guidance_scale is None else guidance_scale
        )

        policy.validate_prompt(prompt)
        policy.validate_negative_prompt(negative_prompt)
        policy.validate_dimensions(width, height)
        policy.validate_steps(resolved_steps)
        policy.validate_guidance_scale(resolved_guidance)
        policy.validate_seed(seed)
        policy.validate_output_name(output_name)
        resolved_operation = (operation or OperationType.TEXT_TO_IMAGE.value).strip().lower()
        if resolved_operation not in {
            OperationType.TEXT_TO_IMAGE.value,
            OperationType.IMAGE_TO_IMAGE.value,
            OperationType.INPAINTING.value,
        }:
            raise OperationUnsupportedError(
                f"Operation '{resolved_operation}' is not supported."
            )

        inference_caps = self._backend.describe_capabilities()
        prepared_source = None
        source_meta = None
        prepared_mask = None
        mask_meta = None
        mask_convention = None
        resolved_strength = None

        if resolved_operation == OperationType.IMAGE_TO_IMAGE.value:
            if not inference_caps.image_to_image_supported:
                raise OperationUnsupportedError(
                    "The current model/backend does not support image_to_image. "
                    "The request was not converted to text-to-image."
                )
            if mask_image_base64 is not None:
                raise GenerationRequestInvalidError(
                    "mask_image is only valid for inpainting.",
                    field_issues={
                        "mask_image": [
                            FieldIssue(
                                code=FieldIssueCode.VALUE_INVALID,
                                message=(
                                    "mask_image is only accepted when operation is inpainting. "
                                    "Image-to-image is full-frame init variation, not masked "
                                    "inpainting."
                                ),
                            )
                        ]
                    },
                )
            if source_image_base64 is None:
                raise GenerationRequestInvalidError(
                    "source_image is required for image_to_image.",
                    field_issues={
                        "source_image": [
                            FieldIssue(
                                code=FieldIssueCode.FIELD_REQUIRED,
                                message=(
                                    "source_image is required when operation is "
                                    "image_to_image. Provide the init/source image, "
                                    "not a reference-conditioning image."
                                ),
                            )
                        ]
                    },
                )
            raw_bytes = decode_source_image_base64(source_image_base64)
            validated_source = validate_source_image(
                raw_bytes=raw_bytes,
                policy=policy,
                media_type=source_image_media_type,
            )
            resolved_strength = (
                policy.default_denoising_strength
                if denoising_strength is None
                else float(denoising_strength)
            )
            policy.validate_denoising_strength(resolved_strength)
            prepared_source = prepare_init_image(validated_source.image, width, height)
            source_meta = validated_source.metadata
        elif resolved_operation == OperationType.INPAINTING.value:
            if not inference_caps.inpainting_supported:
                raise OperationUnsupportedError(
                    "The current model/backend does not support inpainting. "
                    "The request was not converted to image_to_image or text_to_image."
                )
            if source_image_base64 is None:
                raise GenerationRequestInvalidError(
                    "source_image is required for inpainting.",
                    field_issues={
                        "source_image": [
                            FieldIssue(
                                code=FieldIssueCode.FIELD_REQUIRED,
                                message=(
                                    "source_image is required when operation is inpainting. "
                                    "Provide the image to keep outside the mask, not a "
                                    "reference-conditioning image."
                                ),
                            )
                        ]
                    },
                )
            if mask_image_base64 is None:
                raise GenerationRequestInvalidError(
                    "mask_image is required for inpainting.",
                    field_issues={
                        "mask_image": [
                            FieldIssue(
                                code=FieldIssueCode.FIELD_REQUIRED,
                                message=(
                                    "mask_image is required when operation is inpainting. "
                                    "White regenerates; black is kept from the source."
                                ),
                            )
                        ]
                    },
                )
            raw_bytes = decode_source_image_base64(source_image_base64)
            validated_source = validate_source_image(
                raw_bytes=raw_bytes,
                policy=policy,
                media_type=source_image_media_type,
                apply_exif=True,
            )
            mask_bytes = decode_mask_image_base64(mask_image_base64)
            validated_mask = validate_mask_image(
                raw_bytes=mask_bytes,
                policy=policy,
                media_type=mask_image_media_type,
            )
            assert_source_mask_dimensions_match(
                source_width=validated_source.metadata.original_width,
                source_height=validated_source.metadata.original_height,
                mask_width=validated_mask.metadata.original_width,
                mask_height=validated_mask.metadata.original_height,
            )
            resolved_strength = (
                policy.default_denoising_strength
                if denoising_strength is None
                else float(denoising_strength)
            )
            policy.validate_denoising_strength(resolved_strength)
            prepared_source = prepare_inpaint_source(validated_source.image, width, height)
            prepared_mask = prepare_inpaint_mask(validated_mask.image, width, height)
            source_meta = validated_source.metadata
            mask_meta = validated_mask.metadata
            mask_convention = MASK_CONVENTION_ID
        else:
            if source_image_base64 is not None:
                raise GenerationRequestInvalidError(
                    "source_image is only valid for image_to_image or inpainting.",
                    field_issues={
                        "source_image": [
                            FieldIssue(
                                code=FieldIssueCode.VALUE_INVALID,
                                message=(
                                    "source_image is the init/latent image and is only "
                                    "accepted when operation is image_to_image or inpainting. "
                                    "It is not a reference-conditioning input."
                                ),
                            )
                        ]
                    },
                )
            if mask_image_base64 is not None:
                raise GenerationRequestInvalidError(
                    "mask_image is only valid for inpainting.",
                    field_issues={
                        "mask_image": [
                            FieldIssue(
                                code=FieldIssueCode.VALUE_INVALID,
                                message="mask_image is only accepted when operation is inpainting.",
                            )
                        ]
                    },
                )
            if denoising_strength is not None:
                raise GenerationRequestInvalidError(
                    "denoising_strength is only valid for image_to_image or inpainting.",
                    field_issues={
                        "denoising_strength": [
                            FieldIssue(
                                code=FieldIssueCode.VALUE_INVALID,
                                message=(
                                    "denoising_strength applies only to image_to_image "
                                    "or inpainting."
                                ),
                                actual=denoising_strength,
                            )
                        ]
                    },
                )

        _validate_provenance(
            identifiers={
                "generation_profile_id": generation_profile_id,
                "prompt_template_id": prompt_template_id,
                "negative_prompt_profile_id": negative_prompt_profile_id,
                "unity_import_profile_id": unity_import_profile_id,
            },
            revisions={
                "generation_profile_revision": generation_profile_revision,
                "prompt_template_revision": prompt_template_revision,
                "negative_prompt_profile_revision": negative_prompt_profile_revision,
            },
            profile_origin=profile_origin,
        )

        supported_types = set(inference_caps.supported_asset_types)
        if asset_type not in supported_types:
            raise AssetTypeUnsupportedError(
                f"Asset type '{asset_type}' is not supported by the current inference backend."
            )

        strategy = (transparency_strategy or TransparencyStrategy.NONE.value).strip().lower()
        if not is_known_transparency_strategy(strategy):
            raise TransparencyStrategyUnsupportedError(
                f"Transparency strategy '{strategy}' is not supported."
            )

        if asset_type == AssetType.TEXTURE.value and strategy != TransparencyStrategy.NONE.value:
            raise TransparencyStrategyUnsupportedError(
                "Transparency processing is not applied to texture assets; "
                "use transparency_strategy 'none'."
            )

        if strategy == TransparencyStrategy.BACKGROUND_REMOVAL.value and (
            self._processing is None or not self._processing.background_remover.available
        ):
            raise BackgroundRemovalUnavailableError(
                "Background removal is required but unavailable. "
                "Enable BACKGROUND_REMOVAL_ENABLED and install the optional "
                "background-removal extra, or select transparency_strategy 'none'."
            )

        resolved_alpha_threshold = (
            settings.default_alpha_threshold if alpha_threshold is None else alpha_threshold
        )
        resolved_alpha_feather = (
            settings.default_alpha_feather if alpha_feather is None else alpha_feather
        )
        resolved_remove_near = (
            settings.default_remove_near_transparent
            if remove_near_transparent is None
            else remove_near_transparent
        )
        resolved_zero_rgb = (
            settings.default_zero_rgb_when_transparent
            if zero_rgb_when_transparent is None
            else zero_rgb_when_transparent
        )

        if (
            not settings.min_alpha_threshold
            <= resolved_alpha_threshold
            <= settings.max_alpha_threshold
        ):
            raise GenerationRequestInvalidError(
                "alpha_threshold is outside the supported range.",
                field_issues={
                    "alpha_threshold": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_INVALID,
                            message="alpha_threshold is outside the supported range.",
                            actual=resolved_alpha_threshold,
                            minimum=settings.min_alpha_threshold,
                            maximum=settings.max_alpha_threshold,
                        )
                    ]
                },
            )
        if not settings.min_alpha_feather <= resolved_alpha_feather <= settings.max_alpha_feather:
            raise GenerationRequestInvalidError(
                "alpha_feather is outside the supported range.",
                field_issues={
                    "alpha_feather": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_INVALID,
                            message="alpha_feather is outside the supported range.",
                            actual=resolved_alpha_feather,
                            minimum=settings.min_alpha_feather,
                            maximum=settings.max_alpha_feather,
                        )
                    ]
                },
            )

        resolved_ppu: float | None = None
        resolved_pivot: str | None = None
        resolved_pivot_x: float | None = None
        resolved_pivot_y: float | None = None
        resolved_atlas: str | None = None

        if asset_type in _SPRITE_ICON_TYPES:
            resolved_ppu = (
                settings.default_pixels_per_unit if pixels_per_unit is None else pixels_per_unit
            )
            if not math.isfinite(resolved_ppu) or resolved_ppu <= 0:
                raise PixelsPerUnitInvalidError(
                    "pixels_per_unit must be a positive finite number.",
                    field_issues={
                        "pixels_per_unit": [
                            FieldIssue(
                                code=FieldIssueCode.VALUE_INVALID,
                                message="pixels_per_unit must be a positive finite number.",
                                actual=resolved_ppu,
                            )
                        ]
                    },
                )
            resolved_pivot = (pivot_mode or settings.default_pivot_mode).strip().lower()
            if not is_known_pivot_mode(resolved_pivot):
                raise PivotInvalidError(
                    f"pivot_mode '{resolved_pivot}' is not supported.",
                    field_issues={
                        "pivot_mode": [
                            FieldIssue(
                                code=FieldIssueCode.VALUE_INVALID,
                                message="pivot_mode must be center, bottom_center, or custom.",
                                actual=resolved_pivot,
                            )
                        ]
                    },
                )
            if resolved_pivot == PivotMode.CUSTOM.value:
                if custom_pivot_x is None or custom_pivot_y is None:
                    raise PivotInvalidError(
                        "custom_pivot_x and custom_pivot_y are required for custom pivot.",
                        field_issues={
                            "custom_pivot": [
                                FieldIssue(
                                    code=FieldIssueCode.FIELD_REQUIRED,
                                    message=(
                                        "custom_pivot_x and custom_pivot_y are required "
                                        "when pivot_mode is custom."
                                    ),
                                )
                            ]
                        },
                    )
                if not (0.0 <= custom_pivot_x <= 1.0 and 0.0 <= custom_pivot_y <= 1.0):
                    raise PivotInvalidError(
                        "custom pivot coordinates must be between 0 and 1.",
                        field_issues={
                            "custom_pivot": [
                                FieldIssue(
                                    code=FieldIssueCode.VALUE_INVALID,
                                    message="custom_pivot_x/y must be in the range 0 to 1.",
                                    actual={"x": custom_pivot_x, "y": custom_pivot_y},
                                )
                            ]
                        },
                    )
                resolved_pivot_x = float(custom_pivot_x)
                resolved_pivot_y = float(custom_pivot_y)
            if atlas_hint is not None:
                hint = atlas_hint.strip()
                if hint and _ATLAS_HINT_PATTERN.fullmatch(hint) is None:
                    raise GenerationRequestInvalidError(
                        "atlas_hint has an invalid format.",
                        field_issues={
                            "atlas_hint": [
                                FieldIssue(
                                    code=FieldIssueCode.FORMAT_INVALID,
                                    message=(
                                        "atlas_hint must be at most 64 characters and contain "
                                        "only letters, digits, underscores, or hyphens."
                                    ),
                                    actual=hint,
                                )
                            ]
                        },
                    )
                resolved_atlas = hint or None
        else:
            # Soft-ignore sprite-only fields for textures (do not store misleading provenance).
            pass

        resolved_tileable = bool(tileable) if tileable is not None else False
        resolved_seam_correction = (
            bool(apply_seam_correction) if apply_seam_correction is not None else False
        )
        resolved_seam_blend = (
            settings.default_seam_width if seam_blend_width is None else int(seam_blend_width)
        )
        resolved_palette = (
            bool(palette_reduction_enabled) if palette_reduction_enabled is not None else False
        )
        resolved_palette_colors = 16 if palette_color_count is None else int(palette_color_count)

        if not 8 <= resolved_seam_blend <= 128:
            raise GenerationRequestInvalidError(
                "seam_blend_width is outside the supported range.",
                field_issues={
                    "seam_blend_width": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_INVALID,
                            message="seam_blend_width must be between 8 and 128.",
                            actual=resolved_seam_blend,
                            minimum=8,
                            maximum=128,
                        )
                    ]
                },
            )
        if not 2 <= resolved_palette_colors <= 256:
            raise GenerationRequestInvalidError(
                "palette_color_count is outside the supported range.",
                field_issues={
                    "palette_color_count": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_INVALID,
                            message="palette_color_count must be between 2 and 256.",
                            actual=resolved_palette_colors,
                            minimum=2,
                            maximum=256,
                        )
                    ]
                },
            )

        if resolved_seam_correction:
            if width != 512 or height != 512:
                raise GenerationRequestInvalidError(
                    "AI seam repair requires exactly 512x512 textures.",
                    field_issues={
                        "width": [
                            FieldIssue(
                                code=FieldIssueCode.VALUE_INVALID,
                                message="AI seam repair requires width and height of 512.",
                                actual={"width": width, "height": height},
                            )
                        ]
                    },
                )
            if (
                self._processing is None
                or not self._processing.seam_inpainter.available
            ):
                raise SeamInpaintUnavailableError(
                    "Local seam inpainting is required for apply_seam_correction "
                    "but is unavailable. Enable SEAM_INPAINT_ENABLED and ensure the "
                    "inpaint model can load, or disable apply_seam_correction."
                )

        safe_name = sanitize_output_name(
            output_name,
            max_length=policy.maximum_output_name_length,
        )

        if seed is None:
            span = policy.maximum_seed - policy.minimum_seed + 1
            resolved_seed = policy.minimum_seed + secrets.randbelow(span)
        else:
            resolved_seed = seed

        request = GenerationRequest(
            prompt=prompt.strip(),
            negative_prompt=negative_prompt.strip(),
            width=width,
            height=height,
            steps=resolved_steps,
            guidance_scale=resolved_guidance,
            seed=resolved_seed,
            output_name=safe_name,
            generation_id=str(uuid.uuid4()),
            generation_profile_id=generation_profile_id,
            generation_profile_revision=generation_profile_revision,
            profile_origin=profile_origin,
            prompt_template_id=prompt_template_id,
            prompt_template_revision=prompt_template_revision,
            negative_prompt_profile_id=negative_prompt_profile_id,
            negative_prompt_profile_revision=negative_prompt_profile_revision,
            unity_import_profile_id=unity_import_profile_id,
            asset_type=asset_type,
            transparency_strategy=strategy,
            alpha_threshold=resolved_alpha_threshold,
            alpha_feather=resolved_alpha_feather,
            remove_near_transparent=resolved_remove_near,
            zero_rgb_when_transparent=resolved_zero_rgb,
            pixels_per_unit=resolved_ppu,
            pivot_mode=resolved_pivot,
            custom_pivot_x=resolved_pivot_x,
            custom_pivot_y=resolved_pivot_y,
            atlas_hint=resolved_atlas,
            tileable=resolved_tileable,
            apply_seam_correction=resolved_seam_correction,
            seam_blend_width=resolved_seam_blend,
            palette_reduction_enabled=resolved_palette,
            palette_color_count=resolved_palette_colors,
            operation=resolved_operation,
            denoising_strength=resolved_strength,
            source_image=prepared_source,
            source_image_meta=source_meta,
            mask_image=prepared_mask,
            mask_image_meta=mask_meta,
            mask_convention=mask_convention,
        )
        if _validation_only.get():
            raise _ValidatedRequestError(request.seed)

        raise_if_cancelled(cancel_event)
        logger.info(
            "Starting generation_id=%s request_id=%s operation=%s asset_type=%s strategy=%s "
            "tileable=%s apply_seam_correction=%s seed=%s size=%sx%s steps=%s "
            "denoising_strength=%s",
            request.generation_id,
            get_request_id(),
            request.operation,
            request.asset_type,
            request.transparency_strategy,
            request.tileable,
            request.apply_seam_correction,
            request.seed,
            request.width,
            request.height,
            request.steps,
            request.denoising_strength,
        )

        needs_background_removal = (
            request.transparency_strategy == TransparencyStrategy.BACKGROUND_REMOVAL.value
        )
        needs_gpu_post_processing = (
            needs_background_removal or request.apply_seam_correction
        )

        with self._generation_lock:
            raise_if_cancelled(cancel_event)
            if self.exclusive_model_vram:
                # Ensure post-processing models are not occupying VRAM during txt2img.
                self._unload_inpaint(reason="before txt2img")
                self._unload_background_removal(reason="before txt2img")

            self._report_progress(on_progress, "generating", total_steps=request.steps)
            generate_kwargs: dict[str, Any] = {}
            generate_params = inspect.signature(self._backend.generate).parameters
            if "cancel_event" in generate_params:
                generate_kwargs["cancel_event"] = cancel_event
            if "on_progress" in generate_params:
                generate_kwargs["on_progress"] = on_progress
            generated = self._backend.generate(request, **generate_kwargs)
            raise_if_cancelled(cancel_event)

            if self.exclusive_model_vram and needs_gpu_post_processing:
                # Hand VRAM to the next GPU post-processing stage.
                self._unload_txt2img(reason="before post-processing")

            self._report_progress(on_progress, "processing")
            processing_result = self._apply_processing(generated, request)
            raise_if_cancelled(cancel_event)

            if self.exclusive_model_vram:
                if request.apply_seam_correction:
                    self._unload_inpaint(reason="after post-processing")
                if needs_background_removal:
                    self._unload_background_removal(reason="after post-processing")

            if request.apply_seam_correction:
                logger.info(
                    "Seam repair generation_id=%s requested=true applied=%s "
                    "implementation=%s scores_before=%s scores_after=%s",
                    request.generation_id,
                    processing_result.seam_correction_applied,
                    processing_result.seam_inpaint_implementation,
                    processing_result.seam_score_before,
                    processing_result.seam_score_after,
                )
            elif processing_result.seam_correction_applied:
                # Should not happen: never claim repair without a request.
                logger.warning(
                    "Seam repair generation_id=%s applied unexpectedly without request",
                    request.generation_id,
                )
            if request.transparency_strategy == "background_removal":
                logger.info(
                    "Transparency generation_id=%s strategy=background_removal "
                    "applied=%s implementation=%s",
                    request.generation_id,
                    processing_result.background_removal_applied,
                    processing_result.background_removal_implementation,
                )
            processed_image = GeneratedImage(
                image=processing_result.image,
                seed=generated.seed,
                width=processing_result.image.width,
                height=processing_result.image.height,
                elapsed_seconds=generated.elapsed_seconds,
                device=generated.device,
                torch_dtype=generated.torch_dtype,
                model_id=generated.model_id,
                model_revision=generated.model_revision,
            )
            self._report_progress(on_progress, "persisting")
            raise_if_cancelled(cancel_event)
            return self._output_service.persist(
                request,
                processed_image,
                processing=processing_result,
            )

    def _apply_processing(
        self,
        generated: GeneratedImage,
        request: GenerationRequest,
    ) -> ProcessingResult:
        alpha_params = AlphaCleanupParams(
            alpha_threshold=request.alpha_threshold,
            alpha_feather=request.alpha_feather,
            remove_near_transparent=request.remove_near_transparent,
            zero_rgb_when_transparent=request.zero_rgb_when_transparent,
        )
        tileable_params = TileableProcessingParams(
            tileable=request.tileable,
            apply_seam_correction=request.apply_seam_correction,
            seam_blend_width=request.seam_blend_width,
            palette_reduction_enabled=request.palette_reduction_enabled,
            palette_color_count=request.palette_color_count,
            inpaint_seed=request.seed,
        )
        if self._processing is not None:
            return self._processing.process(
                generated.image,
                transparency_strategy=request.transparency_strategy,
                alpha_params=alpha_params,
                preserve_original=self._settings.preserve_original_image,
                tileable_params=tileable_params,
                exclusive_vram=self.exclusive_model_vram,
            )

        # No pipeline registered: still apply local tileable steps when requested.
        from unity_ai_assets.processing.pipeline import _wrap_fields
        from unity_ai_assets.processing.tileable import apply_tileable_processing

        tileable_result = apply_tileable_processing(
            generated.image,
            tileable_params,
            preserve_original=self._settings.preserve_original_image,
            seam_inpainter=None,
        )
        wrap = _wrap_fields(tileable_result.wrap_before, tileable_result.wrap_after)
        return ProcessingResult(
            image=tileable_result.image,
            original_image=tileable_result.original_image,
            transparency_strategy=request.transparency_strategy,
            background_removal_applied=False,
            background_removal_implementation=None,
            alpha_cleanup_applied=False,
            alpha_threshold=alpha_params.alpha_threshold,
            alpha_feather=alpha_params.alpha_feather,
            remove_near_transparent=alpha_params.remove_near_transparent,
            zero_rgb_when_transparent=alpha_params.zero_rgb_when_transparent,
            tileable=tileable_result.tileable,
            seam_correction_applied=tileable_result.seam_correction_applied,
            palette_reduction_applied=tileable_result.palette_reduction_applied,
            seam_blend_width=request.seam_blend_width,
            palette_color_count=request.palette_color_count,
            seam_score_before=(
                None
                if tileable_result.seam_analysis_before is None
                else tileable_result.seam_analysis_before.combined_score
            ),
            seam_score_after=(
                None
                if tileable_result.seam_analysis_after is None
                else tileable_result.seam_analysis_after.combined_score
            ),
            horizontal_seam_score=(
                None
                if tileable_result.seam_analysis_after is None
                else tileable_result.seam_analysis_after.horizontal_score
            ),
            vertical_seam_score=(
                None
                if tileable_result.seam_analysis_after is None
                else tileable_result.seam_analysis_after.vertical_score
            ),
            horizontal_wrap_discontinuity=wrap["horizontal_wrap_discontinuity"],
            vertical_wrap_discontinuity=wrap["vertical_wrap_discontinuity"],
            seam_inpaint_implementation=tileable_result.seam_inpaint_implementation,
        )
