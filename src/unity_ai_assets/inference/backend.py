"""Inference backend abstraction.

The rest of the application depends only on this protocol so Diffusers
(or any future engine) can be swapped without touching API or domain layers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from unity_ai_assets.domain.capabilities import InferenceCapabilities
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest


@runtime_checkable
class ImageGenerationBackend(Protocol):
    """Contract for text-to-image inference engines."""

    def generate(self, request: GenerationRequest) -> GeneratedImage:
        """Generate a single image for the given request."""
        ...

    def describe_capabilities(self) -> InferenceCapabilities:
        """Report implemented operations and runtime facts without loading weights."""
        ...

    def unload_weights(self) -> bool:
        """Release loaded inference weights when possible. Returns True if unloaded."""
        ...

    @property
    def model_loaded(self) -> bool:
        """Whether the underlying model is currently loaded."""
        ...

    @property
    def device_name(self) -> str:
        """Resolved device used for inference (e.g. cuda, cpu, mps)."""
        ...
