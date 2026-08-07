"""Orchestrates validation, inference, and persistence for texture generation."""

from __future__ import annotations

import re
import secrets
import threading
import uuid
from typing import TYPE_CHECKING

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import FieldIssue, GenerationRequestInvalidError
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.core.request_context import get_request_id
from unity_ai_assets.domain.generation import GenerationRequest, GenerationResult
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.services.output_service import OutputService, sanitize_output_name

if TYPE_CHECKING:
    from unity_ai_assets.inference.backend import ImageGenerationBackend

logger = get_logger(__name__)
_PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


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
        generation_profile_id: str | None = None,
        generation_profile_revision: int | None = None,
        profile_origin: str | None = None,
        prompt_template_id: str | None = None,
        prompt_template_revision: int | None = None,
        negative_prompt_profile_id: str | None = None,
        negative_prompt_profile_revision: int | None = None,
        unity_import_profile_id: str | None = None,
        asset_type: str = "texture",
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
