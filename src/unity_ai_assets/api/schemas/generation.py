"""API request/response schemas for texture generation and health."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from unity_ai_assets.core.version import GENERATION_MANIFEST_SCHEMA_VERSION

_PROFILE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"


class TextureGenerationRequest(BaseModel):
    """HTTP body for POST /api/v1/generations/textures.

    Soft bounds here catch obviously invalid shapes early; authoritative
    validation against GenerationPolicy happens in GenerationService and must
    reject rather than coerce.
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
    asset_type: Literal["texture"] = "texture"

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value


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
