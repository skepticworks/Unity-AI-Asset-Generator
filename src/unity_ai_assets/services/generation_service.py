"""Orchestrates validation, inference, and persistence for texture generation."""

from __future__ import annotations

import secrets
import threading
import uuid
from typing import TYPE_CHECKING

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.core.request_context import get_request_id
from unity_ai_assets.domain.generation import GenerationRequest, GenerationResult
from unity_ai_assets.domain.generation_policy import GenerationPolicy
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
        policy: GenerationPolicy | None = None,
    ) -> None:
        self._backend = backend
        self._output_service = output_service
        self._settings = settings
        self._policy = policy or GenerationPolicy.from_settings(settings)
        self._generation_lock = threading.Lock()

    @property
    def backend(self) -> ImageGenerationBackend:
        return self._backend

    @property
    def policy(self) -> GenerationPolicy:
        return self._policy

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
    ) -> GenerationResult:
        """Validate inputs against policy, run inference under a lock, and persist."""
        policy = self._policy
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
        )

        logger.info(
            "Starting generation_id=%s request_id=%s seed=%s size=%sx%s steps=%s",
            request.generation_id,
            get_request_id(),
            request.seed,
            request.width,
            request.height,
            request.steps,
        )

        with self._generation_lock:
            generated = self._backend.generate(request)
            return self._output_service.persist(request, generated)
