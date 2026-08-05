"""API request/response schemas for texture generation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TextureGenerationRequest(BaseModel):
    """HTTP body for POST /api/v1/generations/textures."""

    prompt: str = Field(..., min_length=1, description="Text prompt for texture generation")
    negative_prompt: str = Field(
        default="",
        description="Optional negative prompt",
    )
    width: int = Field(default=512, ge=8)
    height: int = Field(default=512, ge=8)
    steps: int = Field(default=25, ge=1, le=150)
    guidance_scale: float = Field(default=7.0, ge=0, le=30)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    output_name: str = Field(default="texture", min_length=1, max_length=64)


class TextureGenerationResponse(BaseModel):
    """Successful generation response."""

    generation_id: str
    status: str
    image_path: str
    metadata_path: str
    seed: int
    width: int
    height: int
    elapsed_seconds: float


class HealthResponse(BaseModel):
    """Health check payload."""

    status: str
    model_loaded: bool
    device: str


class ErrorResponse(BaseModel):
    """Stable API error envelope."""

    error: str
    code: str
    message: str
