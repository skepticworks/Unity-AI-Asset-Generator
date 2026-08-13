"""Authoritative public generation constraints.

This module is the single source of truth for generation limits used by
request validation, capability reporting, defaults, and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import FieldIssue, GenerationRequestInvalidError

if TYPE_CHECKING:
    from unity_ai_assets.core.config import Settings


@dataclass(frozen=True, slots=True)
class GenerationPolicy:
    """Immutable generation constraint set derived from validated settings."""

    minimum_width: int
    maximum_width: int
    minimum_height: int
    maximum_height: int
    width_multiple: int
    height_multiple: int
    minimum_steps: int
    maximum_steps: int
    default_steps: int
    minimum_guidance_scale: float
    maximum_guidance_scale: float
    default_guidance_scale: float
    minimum_seed: int
    maximum_seed: int
    maximum_prompt_length: int
    maximum_negative_prompt_length: int
    maximum_output_name_length: int
    maximum_concurrent_generations: int
    default_scheduler: str
    negative_prompt_supported: bool = True
    seed_random_when_omitted: bool = True
    minimum_denoising_strength: float = 0.0
    maximum_denoising_strength: float = 1.0
    default_denoising_strength: float = 0.75
    maximum_source_image_bytes: int = 10 * 1024 * 1024
    supported_source_image_formats: tuple[str, ...] = ("png", "jpeg", "webp")
    maximum_mask_image_bytes: int = 10 * 1024 * 1024
    supported_mask_image_formats: tuple[str, ...] = ("png", "jpeg", "webp")

    @classmethod
    def from_settings(cls, settings: Settings) -> GenerationPolicy:
        """Build a policy from validated application settings."""
        return cls(
            minimum_width=settings.min_width,
            maximum_width=settings.max_width,
            minimum_height=settings.min_height,
            maximum_height=settings.max_height,
            width_multiple=settings.width_multiple,
            height_multiple=settings.height_multiple,
            minimum_steps=settings.min_steps,
            maximum_steps=settings.max_steps,
            default_steps=settings.default_steps,
            minimum_guidance_scale=settings.min_guidance_scale,
            maximum_guidance_scale=settings.max_guidance_scale,
            default_guidance_scale=settings.default_guidance_scale,
            minimum_seed=settings.min_seed,
            maximum_seed=settings.max_seed,
            maximum_prompt_length=settings.max_prompt_length,
            maximum_negative_prompt_length=settings.max_negative_prompt_length,
            maximum_output_name_length=settings.max_output_name_length,
            maximum_concurrent_generations=settings.max_concurrent_generations,
            default_scheduler=settings.default_scheduler,
            minimum_denoising_strength=settings.min_denoising_strength,
            maximum_denoising_strength=settings.max_denoising_strength,
            default_denoising_strength=settings.default_denoising_strength,
            maximum_source_image_bytes=settings.max_source_image_bytes,
            supported_source_image_formats=tuple(settings.supported_source_image_formats),
            maximum_mask_image_bytes=settings.max_mask_image_bytes,
            supported_mask_image_formats=tuple(settings.supported_mask_image_formats),
        )

    def validate_prompt(self, prompt: str | None) -> None:
        """Validate the primary prompt (required, non-empty, length-bounded)."""
        if prompt is None or not str(prompt).strip():
            raise GenerationRequestInvalidError(
                "prompt is required and must not be empty",
                field_issues={
                    "prompt": [
                        FieldIssue(
                            code=FieldIssueCode.FIELD_REQUIRED,
                            message="Prompt is required and must not be empty.",
                        )
                    ]
                },
            )
        text = str(prompt)
        if len(text) > self.maximum_prompt_length:
            raise GenerationRequestInvalidError(
                "prompt exceeds maximum length",
                field_issues={
                    "prompt": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_TOO_LONG,
                            message=(
                                f"Prompt must be at most {self.maximum_prompt_length} characters."
                            ),
                            actual=len(text),
                            maximum=self.maximum_prompt_length,
                        )
                    ]
                },
            )

    def validate_negative_prompt(self, negative_prompt: str | None) -> None:
        """Validate optional negative prompt length when provided."""
        if negative_prompt is None:
            return
        text = str(negative_prompt)
        if len(text) > self.maximum_negative_prompt_length:
            raise GenerationRequestInvalidError(
                "negative_prompt exceeds maximum length",
                field_issues={
                    "negative_prompt": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_TOO_LONG,
                            message=(
                                "Negative prompt must be at most "
                                f"{self.maximum_negative_prompt_length} characters."
                            ),
                            actual=len(text),
                            maximum=self.maximum_negative_prompt_length,
                        )
                    ]
                },
            )

    def validate_dimensions(self, width: int, height: int) -> None:
        """Validate width and height against range and multiple constraints."""
        issues: dict[str, list[FieldIssue]] = {}
        self._check_dimension(
            "width", width, self.minimum_width, self.maximum_width, self.width_multiple, issues
        )
        self._check_dimension(
            "height", height, self.minimum_height, self.maximum_height, self.height_multiple, issues
        )
        if issues:
            raise GenerationRequestInvalidError(
                "generation dimensions are invalid",
                field_issues=issues,
            )

    def validate_steps(self, steps: int) -> None:
        """Validate inference step count."""
        if steps < self.minimum_steps:
            raise GenerationRequestInvalidError(
                "steps below minimum",
                field_issues={
                    "steps": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_BELOW_MINIMUM,
                            message=f"Steps must be at least {self.minimum_steps}.",
                            actual=steps,
                            minimum=self.minimum_steps,
                        )
                    ]
                },
            )
        if steps > self.maximum_steps:
            raise GenerationRequestInvalidError(
                "steps above maximum",
                field_issues={
                    "steps": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                            message=f"Steps must be at most {self.maximum_steps}.",
                            actual=steps,
                            maximum=self.maximum_steps,
                        )
                    ]
                },
            )

    def validate_guidance_scale(self, guidance_scale: float) -> None:
        """Validate guidance scale."""
        if guidance_scale < self.minimum_guidance_scale:
            raise GenerationRequestInvalidError(
                "guidance_scale below minimum",
                field_issues={
                    "guidance_scale": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_BELOW_MINIMUM,
                            message=(
                                f"Guidance scale must be at least {self.minimum_guidance_scale}."
                            ),
                            actual=guidance_scale,
                            minimum=self.minimum_guidance_scale,
                        )
                    ]
                },
            )
        if guidance_scale > self.maximum_guidance_scale:
            raise GenerationRequestInvalidError(
                "guidance_scale above maximum",
                field_issues={
                    "guidance_scale": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                            message=(
                                f"Guidance scale must be at most {self.maximum_guidance_scale}."
                            ),
                            actual=guidance_scale,
                            maximum=self.maximum_guidance_scale,
                        )
                    ]
                },
            )

    def validate_seed(self, seed: int | None) -> None:
        """Validate an explicitly supplied seed (None means random)."""
        if seed is None:
            return
        if seed < self.minimum_seed:
            raise GenerationRequestInvalidError(
                "seed below minimum",
                field_issues={
                    "seed": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_BELOW_MINIMUM,
                            message=f"Seed must be at least {self.minimum_seed}.",
                            actual=seed,
                            minimum=self.minimum_seed,
                        )
                    ]
                },
            )
        if seed > self.maximum_seed:
            raise GenerationRequestInvalidError(
                "seed above maximum",
                field_issues={
                    "seed": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                            message=f"Seed must be at most {self.maximum_seed}.",
                            actual=seed,
                            maximum=self.maximum_seed,
                        )
                    ]
                },
            )

    def validate_output_name(self, output_name: str) -> None:
        """Validate output basename length and path-safety (format checked separately)."""
        name = output_name.strip() if output_name is not None else ""
        if not name:
            raise GenerationRequestInvalidError(
                "output_name must not be empty",
                field_issues={
                    "output_name": [
                        FieldIssue(
                            code=FieldIssueCode.FIELD_REQUIRED,
                            message="Output name is required.",
                        )
                    ]
                },
            )
        if len(name) > self.maximum_output_name_length:
            raise GenerationRequestInvalidError(
                "output_name exceeds maximum length",
                field_issues={
                    "output_name": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_TOO_LONG,
                            message=(
                                "Output name must be at most "
                                f"{self.maximum_output_name_length} characters."
                            ),
                            actual=len(name),
                            maximum=self.maximum_output_name_length,
                        )
                    ]
                },
            )

    @staticmethod
    def _check_dimension(
        field: str,
        value: int,
        minimum: int,
        maximum: int,
        multiple: int,
        issues: dict[str, list[FieldIssue]],
    ) -> None:
        field_issues: list[FieldIssue] = []
        if value < minimum:
            field_issues.append(
                FieldIssue(
                    code=FieldIssueCode.VALUE_BELOW_MINIMUM,
                    message=f"{field.capitalize()} must be at least {minimum}.",
                    actual=value,
                    minimum=minimum,
                )
            )
        if value > maximum:
            field_issues.append(
                FieldIssue(
                    code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                    message=f"{field.capitalize()} must be at most {maximum}.",
                    actual=value,
                    maximum=maximum,
                )
            )
        if value % multiple != 0:
            field_issues.append(
                FieldIssue(
                    code=FieldIssueCode.VALUE_NOT_MULTIPLE,
                    message=f"{field.capitalize()} must be divisible by {multiple}.",
                    actual=value,
                    expected_multiple=multiple,
                )
            )
        if field_issues:
            issues[field] = field_issues

    def validate_denoising_strength(self, strength: float) -> None:
        """Validate img2img denoising strength (init-image influence, not IP-Adapter)."""
        if strength < self.minimum_denoising_strength:
            raise GenerationRequestInvalidError(
                "denoising_strength below minimum",
                field_issues={
                    "denoising_strength": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_BELOW_MINIMUM,
                            message=(
                                "Denoising strength must be at least "
                                f"{self.minimum_denoising_strength}."
                            ),
                            actual=strength,
                            minimum=self.minimum_denoising_strength,
                        )
                    ]
                },
            )
        if strength > self.maximum_denoising_strength:
            raise GenerationRequestInvalidError(
                "denoising_strength above maximum",
                field_issues={
                    "denoising_strength": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                            message=(
                                "Denoising strength must be at most "
                                f"{self.maximum_denoising_strength}."
                            ),
                            actual=strength,
                            maximum=self.maximum_denoising_strength,
                        )
                    ]
                },
            )


def validate_policy_settings(
    *,
    min_width: int,
    max_width: int,
    min_height: int,
    max_height: int,
    width_multiple: int,
    height_multiple: int,
    min_steps: int,
    max_steps: int,
    default_steps: int,
    min_guidance_scale: float,
    max_guidance_scale: float,
    default_guidance_scale: float,
    min_seed: int,
    max_seed: int,
    max_prompt_length: int,
    max_negative_prompt_length: int,
    max_output_name_length: int,
    max_concurrent_generations: int,
    min_denoising_strength: float = 0.0,
    max_denoising_strength: float = 1.0,
    default_denoising_strength: float = 0.75,
    max_source_image_bytes: int = 10 * 1024 * 1024,
    max_mask_image_bytes: int = 10 * 1024 * 1024,
) -> None:
    """Reject invalid policy configuration combinations at startup."""
    errors: list[str] = []

    if width_multiple <= 0:
        errors.append("WIDTH_MULTIPLE must be positive")
    if height_multiple <= 0:
        errors.append("HEIGHT_MULTIPLE must be positive")
    if min_width > max_width:
        errors.append("MIN_WIDTH must not exceed MAX_WIDTH")
    if min_height > max_height:
        errors.append("MIN_HEIGHT must not exceed MAX_HEIGHT")
    if min_width % width_multiple != 0 if width_multiple > 0 else False:
        errors.append("MIN_WIDTH must be divisible by WIDTH_MULTIPLE")
    if max_width % width_multiple != 0 if width_multiple > 0 else False:
        errors.append("MAX_WIDTH must be divisible by WIDTH_MULTIPLE")
    if min_height % height_multiple != 0 if height_multiple > 0 else False:
        errors.append("MIN_HEIGHT must be divisible by HEIGHT_MULTIPLE")
    if max_height % height_multiple != 0 if height_multiple > 0 else False:
        errors.append("MAX_HEIGHT must be divisible by HEIGHT_MULTIPLE")

    if min_steps > max_steps:
        errors.append("MIN_STEPS must not exceed MAX_STEPS")
    if not (min_steps <= default_steps <= max_steps):
        errors.append("DEFAULT_STEPS must be within MIN_STEPS..MAX_STEPS")

    if min_guidance_scale > max_guidance_scale:
        errors.append("MIN_GUIDANCE_SCALE must not exceed MAX_GUIDANCE_SCALE")
    if not (min_guidance_scale <= default_guidance_scale <= max_guidance_scale):
        errors.append(
            "DEFAULT_GUIDANCE_SCALE must be within MIN_GUIDANCE_SCALE..MAX_GUIDANCE_SCALE"
        )

    if min_seed > max_seed:
        errors.append("MIN_SEED must not exceed MAX_SEED")
    if min_seed < 0:
        errors.append("MIN_SEED must be non-negative")

    if max_prompt_length < 1:
        errors.append("MAX_PROMPT_LENGTH must be positive")
    if max_negative_prompt_length < 0:
        errors.append("MAX_NEGATIVE_PROMPT_LENGTH must be non-negative")
    if max_output_name_length < 1:
        errors.append("MAX_OUTPUT_NAME_LENGTH must be positive")
    if max_concurrent_generations < 1:
        errors.append("MAX_CONCURRENT_GENERATIONS must be at least 1")

    if min_denoising_strength > max_denoising_strength:
        errors.append("MIN_DENOISING_STRENGTH must not exceed MAX_DENOISING_STRENGTH")
    if not (min_denoising_strength <= default_denoising_strength <= max_denoising_strength):
        errors.append(
            "DEFAULT_DENOISING_STRENGTH must be within "
            "MIN_DENOISING_STRENGTH..MAX_DENOISING_STRENGTH"
        )
    if min_denoising_strength < 0.0:
        errors.append("MIN_DENOISING_STRENGTH must be at least 0")
    if max_denoising_strength > 1.0:
        errors.append("MAX_DENOISING_STRENGTH must be at most 1")
    if max_source_image_bytes < 1:
        errors.append("MAX_SOURCE_IMAGE_BYTES must be positive")
    if max_mask_image_bytes < 1:
        errors.append("MAX_MASK_IMAGE_BYTES must be positive")

    if errors:
        raise ValueError("; ".join(errors))
