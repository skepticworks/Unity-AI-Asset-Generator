"""Capability checks for profiles and resolved settings."""

from __future__ import annotations

from collections.abc import Collection

from unity_ai_assets.profiles.constants import CompatibilityReasonCode, CompatibilityState
from unity_ai_assets.profiles.models import (
    CompatibilityIssue,
    CompatibilityResult,
    GenerationProfile,
    ResolvedGenerationSettings,
)


def _issue(
    issues: list[CompatibilityIssue],
    code: CompatibilityReasonCode,
    message: str,
    field: str,
) -> None:
    issues.append(CompatibilityIssue(code.value, message, field))


def _evaluate_values(
    *,
    asset_type: str,
    width: int,
    height: int,
    steps: int,
    guidance_scale: float,
    seed: int | None,
    prompt: str | None,
    negative_prompt: str | None,
    supported_asset_types: Collection[str],
    negative_prompt_supported: bool,
    minimum_width: int,
    maximum_width: int,
    minimum_height: int,
    maximum_height: int,
    width_multiple: int,
    height_multiple: int,
    minimum_steps: int,
    maximum_steps: int,
    minimum_guidance: float,
    maximum_guidance: float,
    minimum_seed: int,
    maximum_seed: int,
    maximum_prompt_length: int,
    maximum_negative_prompt_length: int,
) -> list[CompatibilityIssue]:
    issues: list[CompatibilityIssue] = []
    if asset_type not in supported_asset_types:
        _issue(
            issues,
            CompatibilityReasonCode.ASSET_TYPE_UNSUPPORTED,
            f"Asset type '{asset_type}' is not supported.",
            "asset_type",
        )
    if not minimum_width <= width <= maximum_width:
        _issue(
            issues,
            CompatibilityReasonCode.WIDTH_OUT_OF_RANGE,
            "Width is outside the supported range.",
            "width",
        )
    if not minimum_height <= height <= maximum_height:
        _issue(
            issues,
            CompatibilityReasonCode.HEIGHT_OUT_OF_RANGE,
            "Height is outside the supported range.",
            "height",
        )
    if width_multiple > 0 and width % width_multiple:
        _issue(
            issues,
            CompatibilityReasonCode.WIDTH_MULTIPLE_INVALID,
            f"Width must be a multiple of {width_multiple}.",
            "width",
        )
    if height_multiple > 0 and height % height_multiple:
        _issue(
            issues,
            CompatibilityReasonCode.HEIGHT_MULTIPLE_INVALID,
            f"Height must be a multiple of {height_multiple}.",
            "height",
        )
    if not minimum_steps <= steps <= maximum_steps:
        _issue(
            issues,
            CompatibilityReasonCode.STEPS_OUT_OF_RANGE,
            "Steps are outside the supported range.",
            "steps",
        )
    if not minimum_guidance <= guidance_scale <= maximum_guidance:
        _issue(
            issues,
            CompatibilityReasonCode.GUIDANCE_OUT_OF_RANGE,
            "Guidance scale is outside the supported range.",
            "guidance_scale",
        )
    if seed is not None and not minimum_seed <= seed <= maximum_seed:
        _issue(
            issues,
            CompatibilityReasonCode.SEED_OUT_OF_RANGE,
            "Seed is outside the supported range.",
            "seed",
        )
    if negative_prompt and not negative_prompt_supported:
        _issue(
            issues,
            CompatibilityReasonCode.NEGATIVE_PROMPT_UNSUPPORTED,
            "Negative prompts are not supported.",
            "negative_prompt",
        )
    if prompt is not None and len(prompt) > maximum_prompt_length:
        _issue(
            issues,
            CompatibilityReasonCode.PROMPT_TOO_LONG,
            "Prompt exceeds the supported maximum length.",
            "prompt",
        )
    if negative_prompt is not None and len(negative_prompt) > maximum_negative_prompt_length:
        _issue(
            issues,
            CompatibilityReasonCode.NEGATIVE_PROMPT_TOO_LONG,
            "Negative prompt exceeds the supported maximum length.",
            "negative_prompt",
        )
    return issues


def evaluate_profile_compatibility(
    profile: GenerationProfile,
    *,
    supported_asset_types: Collection[str],
    negative_prompt_supported: bool,
    minimum_width: int = 1,
    maximum_width: int = 2**31 - 1,
    minimum_height: int = 1,
    maximum_height: int = 2**31 - 1,
    width_multiple: int = 1,
    height_multiple: int = 1,
    minimum_steps: int = 1,
    maximum_steps: int = 2**31 - 1,
    minimum_guidance: float = 0.0,
    maximum_guidance: float = float("inf"),
    minimum_seed: int = 0,
    maximum_seed: int = 2**32 - 1,
    maximum_prompt_length: int = 2**31 - 1,
    maximum_negative_prompt_length: int = 2**31 - 1,
    import_profile_ids: Collection[str] = (),
    template_ids: Collection[str] = (),
    negative_ids: Collection[str] = (),
    operation_supported: bool = True,
) -> CompatibilityResult:
    """Evaluate profile defaults and references without coercing values."""
    defaults = profile.generation_defaults
    issues = _evaluate_values(
        asset_type=profile.asset_type,
        width=defaults.width,
        height=defaults.height,
        steps=defaults.steps,
        guidance_scale=defaults.guidance_scale,
        seed=defaults.fixed_seed,
        prompt=None,
        negative_prompt=", ".join(profile.additional_negative_terms),
        supported_asset_types=supported_asset_types,
        negative_prompt_supported=negative_prompt_supported,
        minimum_width=minimum_width,
        maximum_width=maximum_width,
        minimum_height=minimum_height,
        maximum_height=maximum_height,
        width_multiple=width_multiple,
        height_multiple=height_multiple,
        minimum_steps=minimum_steps,
        maximum_steps=maximum_steps,
        minimum_guidance=minimum_guidance,
        maximum_guidance=maximum_guidance,
        minimum_seed=minimum_seed,
        maximum_seed=maximum_seed,
        maximum_prompt_length=maximum_prompt_length,
        maximum_negative_prompt_length=maximum_negative_prompt_length,
    )
    if not operation_supported:
        _issue(
            issues,
            CompatibilityReasonCode.OPERATION_UNSUPPORTED,
            "Text-to-image generation is not supported.",
            "operation",
        )
    references = (
        (
            profile.unity.import_profile_id,
            import_profile_ids,
            CompatibilityReasonCode.IMPORT_PROFILE_UNKNOWN,
            "unity.import_profile_id",
        ),
        (
            profile.template_id,
            template_ids,
            CompatibilityReasonCode.TEMPLATE_UNKNOWN,
            "prompt.template_id",
        ),
        (
            profile.negative_prompt_profile_id,
            negative_ids,
            CompatibilityReasonCode.NEGATIVE_PROFILE_UNKNOWN,
            "negative_prompt.profile_id",
        ),
    )
    for value, known, code, field in references:
        if value not in known:
            _issue(issues, code, f"Referenced identifier '{value}' is unknown.", field)
    state = CompatibilityState.COMPATIBLE if not issues else CompatibilityState.INCOMPATIBLE
    return CompatibilityResult(state, tuple(issues))


def evaluate_resolved_settings(
    settings: ResolvedGenerationSettings,
    *,
    supported_asset_types: Collection[str],
    negative_prompt_supported: bool,
    minimum_width: int = 1,
    maximum_width: int = 2**31 - 1,
    minimum_height: int = 1,
    maximum_height: int = 2**31 - 1,
    width_multiple: int = 1,
    height_multiple: int = 1,
    minimum_steps: int = 1,
    maximum_steps: int = 2**31 - 1,
    minimum_guidance: float = 0.0,
    maximum_guidance: float = float("inf"),
    minimum_seed: int = 0,
    maximum_seed: int = 2**32 - 1,
    maximum_prompt_length: int = 2**31 - 1,
    maximum_negative_prompt_length: int = 2**31 - 1,
) -> CompatibilityResult:
    issues = _evaluate_values(
        asset_type=settings.asset_type,
        width=settings.width,
        height=settings.height,
        steps=settings.steps,
        guidance_scale=settings.guidance_scale,
        seed=settings.seed,
        prompt=settings.prompt,
        negative_prompt=settings.negative_prompt,
        supported_asset_types=supported_asset_types,
        negative_prompt_supported=negative_prompt_supported,
        minimum_width=minimum_width,
        maximum_width=maximum_width,
        minimum_height=minimum_height,
        maximum_height=maximum_height,
        width_multiple=width_multiple,
        height_multiple=height_multiple,
        minimum_steps=minimum_steps,
        maximum_steps=maximum_steps,
        minimum_guidance=minimum_guidance,
        maximum_guidance=maximum_guidance,
        minimum_seed=minimum_seed,
        maximum_seed=maximum_seed,
        maximum_prompt_length=maximum_prompt_length,
        maximum_negative_prompt_length=maximum_negative_prompt_length,
    )
    state = CompatibilityState.COMPATIBLE if not issues else CompatibilityState.INCOMPATIBLE
    return CompatibilityResult(state, tuple(issues))
