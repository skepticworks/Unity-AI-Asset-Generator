"""API schema package."""

from unity_ai_assets.api.schemas.generation import (
    ErrorResponse,
    HealthResponse,
    TextureGenerationRequest,
    TextureGenerationResponse,
)

__all__ = [
    "ErrorResponse",
    "HealthResponse",
    "TextureGenerationRequest",
    "TextureGenerationResponse",
]
