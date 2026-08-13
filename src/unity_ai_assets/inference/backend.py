"""Inference backend abstraction.

The rest of the application depends only on this protocol so Diffusers
(or any future engine) can be swapped without touching API or domain layers.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from unity_ai_assets.domain.capabilities import InferenceCapabilities
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest

ProgressHook = Callable[[str, int | None, int | None], None]


@runtime_checkable
class ImageGenerationBackend(Protocol):
    """Contract for text-to-image inference engines."""

    def generate(
        self,
        request: GenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
        on_progress: ProgressHook | None = None,
    ) -> GeneratedImage:
        """Generate a single image for the given request.

        Optional ``cancel_event`` should be checked at the safest available
        interruption point. ``on_progress`` may report truthful step counts
        when the pipeline provides them; do not invent percentages.
        """
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
