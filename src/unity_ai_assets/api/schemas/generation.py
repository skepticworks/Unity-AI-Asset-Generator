"""API request/response schemas for texture generation and health."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from unity_ai_assets.core.version import GENERATION_MANIFEST_SCHEMA_VERSION
from unity_ai_assets.domain.generation_policy import GenerationPolicy


def build_texture_request_schema(policy: GenerationPolicy) -> type[BaseModel]:
    """Build a request model whose Field constraints mirror the authoritative policy.

    FastAPI route handlers typically use TextureGenerationRequest with deferred
    authoritative validation in GenerationService; this helper exists for tests
    that need policy-aligned Field metadata.
    """

    class DynamicTextureGenerationRequest(BaseModel):
        prompt: str = Field(..., min_length=1, max_length=policy.maximum_prompt_length)
        negative_prompt: str = Field(default="", max_length=policy.maximum_negative_prompt_length)
        width: int = Field(
            default=512,
            ge=policy.minimum_width,
            le=policy.maximum_width,
        )
        height: int = Field(
            default=512,
            ge=policy.minimum_height,
            le=policy.maximum_height,
        )
        steps: int = Field(
            default=policy.default_steps,
            ge=policy.minimum_steps,
            le=policy.maximum_steps,
        )
        guidance_scale: float = Field(
            default=policy.default_guidance_scale,
            ge=policy.minimum_guidance_scale,
            le=policy.maximum_guidance_scale,
        )
        seed: int | None = Field(
            default=None,
            ge=policy.minimum_seed,
            le=policy.maximum_seed,
        )
        output_name: str = Field(
            default="texture",
            min_length=1,
            max_length=policy.maximum_output_name_length,
        )

    return DynamicTextureGenerationRequest


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
    # Deprecated: retained temporarily for local debugging / older clients.
    # Unity package must not depend on these. Planned removal after Milestone 4.
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


class ErrorFieldIssue(BaseModel):
    """Field-level issue inside the stable error envelope."""

    code: str
    message: str
    actual: Any | None = None
    minimum: Any | None = None
    maximum: Any | None = None
    expected_multiple: int | None = None


class ErrorBody(BaseModel):
    """Inner error object."""

    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Stable API error envelope."""

    error: ErrorBody


# Prevent unused import warnings when validators are added later.
_ = model_validator
