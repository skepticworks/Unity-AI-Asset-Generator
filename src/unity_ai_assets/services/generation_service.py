"""Orchestrates validation, inference, and persistence for texture generation."""

from __future__ import annotations

import secrets
import threading
import uuid
from typing import TYPE_CHECKING

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import InvalidGenerationParametersError
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.generation import GenerationRequest, GenerationResult
from unity_ai_assets.services.output_service import OutputService, sanitize_output_name

if TYPE_CHECKING:
    from unity_ai_assets.inference.backend import ImageGenerationBackend

logger = get_logger(__name__)


class GenerationService:
    """Coordinates a single text-to-image generation request."""

    def __init__(
        self,
        backend: ImageGenerationBackend,
        output_service: OutputService,
        settings: Settings,
    ) -> None:
        self._backend = backend
        self._output_service = output_service
        self._settings = settings
        self._generation_lock = threading.Lock()

    @property
    def backend(self) -> ImageGenerationBackend:
        return self._backend

    def generate_texture(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 25,
        guidance_scale: float = 7.0,
        seed: int | None = None,
        output_name: str = "texture",
    ) -> GenerationResult:
        """Validate inputs, run inference under a lock, and persist outputs."""
        self._validate_prompt(prompt)
        self._validate_dimensions(width, height)
        self._validate_steps(steps)
        self._validate_guidance(guidance_scale)
        safe_name = sanitize_output_name(output_name)
        resolved_seed = seed if seed is not None else secrets.randbits(32)

        request = GenerationRequest(
            prompt=prompt.strip(),
            negative_prompt=negative_prompt.strip(),
            width=width,
            height=height,
            steps=steps,
            guidance_scale=guidance_scale,
            seed=resolved_seed,
            output_name=safe_name,
            generation_id=str(uuid.uuid4()),
        )

        logger.info(
            "Starting generation_id=%s seed=%s size=%sx%s steps=%s",
            request.generation_id,
            request.seed,
            request.width,
            request.height,
            request.steps,
        )

        # Serialize GPU/CPU diffusion calls for correctness on a single worker.
        with self._generation_lock:
            generated = self._backend.generate(request)
            return self._output_service.persist(request, generated)

    def _validate_prompt(self, prompt: str) -> None:
        if prompt is None or not str(prompt).strip():
            raise InvalidGenerationParametersError("prompt is required and must not be empty")

    def _validate_dimensions(self, width: int, height: int) -> None:
        for label, value in (("width", width), ("height", height)):
            if value <= 0:
                raise InvalidGenerationParametersError(f"{label} must be a positive integer")
            if value % 8 != 0:
                raise InvalidGenerationParametersError(
                    f"{label} must be divisible by 8 (received {value})"
                )
        if width > self._settings.max_width:
            raise InvalidGenerationParametersError(
                f"width {width} exceeds configured MAX_WIDTH ({self._settings.max_width})"
            )
        if height > self._settings.max_height:
            raise InvalidGenerationParametersError(
                f"height {height} exceeds configured MAX_HEIGHT ({self._settings.max_height})"
            )

    @staticmethod
    def _validate_steps(steps: int) -> None:
        if steps < 1 or steps > 150:
            raise InvalidGenerationParametersError("steps must be between 1 and 150")

    @staticmethod
    def _validate_guidance(guidance_scale: float) -> None:
        if guidance_scale < 0 or guidance_scale > 30:
            raise InvalidGenerationParametersError("guidance_scale must be between 0 and 30")
