"""API request/response schemas for texture generation and health."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from unity_ai_assets.core.version import GENERATION_MANIFEST_SCHEMA_VERSION
from unity_ai_assets.domain.enums import PivotMode, TransparencyStrategy

_PROFILE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
_ATLAS_HINT_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"


class SourceImagePayload(BaseModel):
    """Uploaded img2img/inpainting init/source image.

    This is the generation starting image (latent/init image), not a
    reference-conditioning or IP-Adapter input.
    """

    content_base64: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded PNG, JPEG, or WebP bytes used as the init/source image",
    )
    media_type: str | None = Field(
        default=None,
        description="Optional IANA media type (image/png, image/jpeg, image/webp)",
    )


class MaskImagePayload(BaseModel):
    """Uploaded inpainting mask.

    Convention: white (255) regenerates; black (0) is kept from the source.
    Alpha is ignored and must not be used as the inpaint region.
    """

    content_base64: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded PNG, JPEG, or WebP mask (white=inpaint, black=keep)",
    )
    media_type: str | None = Field(
        default=None,
        description="Optional IANA media type (image/png, image/jpeg, image/webp)",
    )


class TextureGenerationRequest(BaseModel):
    """HTTP body for POST /api/v1/generations/textures.

    Soft bounds here catch obviously invalid shapes early; authoritative
    validation against GenerationPolicy happens in GenerationService and must
    reject rather than coerce.

    Sprite/icon processing fields are optional and ignored for textures when
    transparency_strategy remains ``none``.
    """

    prompt: str = Field(..., min_length=1, description="Text prompt for texture generation")
    negative_prompt: str = Field(default="", description="Optional negative prompt")
    width: int = Field(default=512)
    height: int = Field(default=512)
    steps: int = Field(default=25)
    guidance_scale: float = Field(default=7.0)
    seed: int | None = Field(default=None)
    output_name: str = Field(default="texture", min_length=1)
    generation_profile_id: str | None = Field(
        default=None, max_length=128, pattern=_PROFILE_ID_PATTERN
    )
    generation_profile_revision: int | None = Field(default=None, ge=1)
    profile_origin: Literal["builtin", "user", "none"] | None = None
    prompt_template_id: str | None = Field(
        default=None, max_length=128, pattern=_PROFILE_ID_PATTERN
    )
    prompt_template_revision: int | None = Field(default=None, ge=1)
    negative_prompt_profile_id: str | None = Field(
        default=None, max_length=128, pattern=_PROFILE_ID_PATTERN
    )
    negative_prompt_profile_revision: int | None = Field(default=None, ge=1)
    unity_import_profile_id: str | None = Field(
        default=None, max_length=128, pattern=_PROFILE_ID_PATTERN
    )
    asset_type: Literal["texture", "sprite", "icon"] = "texture"
    transparency_strategy: Literal["none", "background_removal"] = TransparencyStrategy.NONE.value
    alpha_threshold: int | None = Field(default=None, ge=0, le=255)
    alpha_feather: int | None = Field(default=None, ge=0, le=64)
    remove_near_transparent: bool | None = None
    zero_rgb_when_transparent: bool | None = None
    pixels_per_unit: float | None = Field(default=None, gt=0)
    pivot_mode: Literal["center", "bottom_center", "custom"] | None = None
    custom_pivot_x: float | None = Field(default=None, ge=0.0, le=1.0)
    custom_pivot_y: float | None = Field(default=None, ge=0.0, le=1.0)
    atlas_hint: str | None = Field(default=None, max_length=64, pattern=_ATLAS_HINT_PATTERN)
    tileable: bool | None = None
    apply_seam_correction: bool | None = None
    seam_blend_width: int | None = Field(default=None, ge=8, le=128)
    palette_reduction_enabled: bool | None = None
    palette_color_count: int | None = Field(default=None, ge=2, le=256)
    operation: Literal["text_to_image", "image_to_image", "inpainting"] = "text_to_image"
    source_image: SourceImagePayload | None = Field(
        default=None,
        description=(
            "Init/source image for image_to_image or inpainting. Required when "
            "operation is image_to_image or inpainting. Not a reference-conditioning input."
        ),
    )
    mask_image: MaskImagePayload | None = Field(
        default=None,
        description=(
            "Inpainting mask. Required when operation is inpainting. White pixels "
            "are regenerated; black pixels are kept. Not valid for image_to_image."
        ),
    )
    denoising_strength: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "How strongly the source init image is denoised (0 keeps it, 1 allows "
            "maximum change). Valid for image_to_image and inpainting."
        ),
    )

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value

    @field_validator("atlas_hint", mode="before")
    @classmethod
    def _empty_atlas_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def _validate_custom_pivot(self) -> TextureGenerationRequest:
        if self.pivot_mode == PivotMode.CUSTOM.value and (
            self.custom_pivot_x is None or self.custom_pivot_y is None
        ):
            raise ValueError(
                "custom_pivot_x and custom_pivot_y are required when pivot_mode is custom"
            )
        if self.operation == "image_to_image":
            if self.source_image is None:
                raise ValueError(
                    "source_image is required when operation is image_to_image "
                    "(init/source image, not reference conditioning)"
                )
            if self.mask_image is not None:
                raise ValueError(
                    "mask_image is only valid for inpainting. "
                    "Image-to-image is full-frame init variation, not masked inpainting."
                )
        elif self.operation == "inpainting":
            if self.source_image is None:
                raise ValueError(
                    "source_image is required when operation is inpainting "
                    "(the image to keep outside the mask, not a reference-conditioning input)"
                )
            if self.mask_image is None:
                raise ValueError(
                    "mask_image is required when operation is inpainting. "
                    "White regenerates; black is kept from the source."
                )
        else:
            if self.source_image is not None:
                raise ValueError(
                    "source_image is only valid for image_to_image or inpainting. "
                    "It is the init/latent image, not a reference-conditioning input."
                )
            if self.mask_image is not None:
                raise ValueError("mask_image is only valid for inpainting")
            if self.denoising_strength is not None:
                raise ValueError(
                    "denoising_strength is only valid for image_to_image or inpainting"
                )
        return self


class GenerationResources(BaseModel):
    """Stable resource links for a completed generation."""

    image: str = Field(description="Relative URL for the generated PNG")
    manifest: str = Field(description="Relative URL for the generation manifest")


class GenerationSchemaVersions(BaseModel):
    """Schema versions relevant to this generation response."""

    generation_manifest: str = Field(default=GENERATION_MANIFEST_SCHEMA_VERSION)


class TextureGenerationResponse(BaseModel):
    """Successful generation response.

    Prefer ``resources`` over deprecated filesystem path fields.
    """

    generation_id: str
    status: str
    operation: str = "text_to_image"
    asset_type: str = "texture"
    seed: int
    width: int
    height: int
    elapsed_seconds: float
    resources: GenerationResources
    schema_versions: GenerationSchemaVersions = Field(
        default_factory=GenerationSchemaVersions,
    )
    # Deprecated wire-compatibility fields retained for older clients.
    # The Unity package no longer consumes these aliases or filesystem paths.
    image_path: str | None = Field(
        default=None,
        description="Deprecated filesystem path for local debugging only",
        deprecated=True,
    )
    metadata_path: str | None = Field(
        default=None,
        description="Deprecated filesystem path for local debugging only",
        deprecated=True,
    )
    image_url: str | None = Field(
        default=None,
        description="Deprecated alias for resources.image",
        deprecated=True,
    )
    metadata_url: str | None = Field(
        default=None,
        description="Deprecated alias for resources.manifest",
        deprecated=True,
    )


class HealthResponse(BaseModel):
    """Lightweight health check payload (not a capability document)."""

    status: str
    application_version: str
    model_loaded: bool
    resolved_device: str
    request_id: str | None = None


class ErrorBody(BaseModel):
    """Inner error object."""

    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Stable API error envelope."""

    error: ErrorBody
