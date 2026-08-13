"""Unit tests for generation policy configuration and validation."""

from __future__ import annotations

import pytest

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import GenerationRequestInvalidError
from unity_ai_assets.domain.generation_policy import GenerationPolicy, validate_policy_settings


def test_policy_from_settings() -> None:
    settings = Settings(max_width=512, max_height=512, default_steps=20)
    policy = GenerationPolicy.from_settings(settings)
    assert policy.maximum_width == 512
    assert policy.default_steps == 20
    assert policy.default_steps == settings.default_steps


def test_policy_rejects_invalid_dimensions() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError) as exc:
        policy.validate_dimensions(510, 512)
    assert exc.value.field_issues["width"][0].code.value == "VALUE_NOT_MULTIPLE"


def test_policy_rejects_steps_out_of_range() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_steps(0)
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_steps(policy.maximum_steps + 1)


def test_policy_rejects_guidance_out_of_range() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_guidance_scale(-0.1)
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_guidance_scale(policy.maximum_guidance_scale + 1)


def test_policy_rejects_prompt_too_long() -> None:
    policy = GenerationPolicy.from_settings(Settings(max_prompt_length=10))
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_prompt("x" * 11)


def test_policy_rejects_negative_prompt_too_long() -> None:
    policy = GenerationPolicy.from_settings(Settings(max_negative_prompt_length=5))
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_negative_prompt("abcdef")


def test_policy_rejects_seed_out_of_range() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_seed(-1)
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_seed(policy.maximum_seed + 1)


def test_policy_rejects_denoising_out_of_range() -> None:
    policy = GenerationPolicy.from_settings(Settings())
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_denoising_strength(-0.01)
    with pytest.raises(GenerationRequestInvalidError):
        policy.validate_denoising_strength(1.01)


def test_invalid_policy_configuration() -> None:
    with pytest.raises(ValueError, match="MIN_WIDTH"):
        validate_policy_settings(
            min_width=1024,
            max_width=512,
            min_height=8,
            max_height=1024,
            width_multiple=8,
            height_multiple=8,
            min_steps=1,
            max_steps=50,
            default_steps=25,
            min_guidance_scale=0.0,
            max_guidance_scale=20.0,
            default_guidance_scale=7.0,
            min_seed=0,
            max_seed=100,
            max_prompt_length=100,
            max_negative_prompt_length=100,
            max_output_name_length=64,
            max_concurrent_generations=1,
        )


def test_settings_reject_invalid_defaults() -> None:
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        Settings(min_steps=10, max_steps=20, default_steps=5)


def test_default_within_reported_range() -> None:
    settings = Settings()
    policy = GenerationPolicy.from_settings(settings)
    assert policy.minimum_steps <= policy.default_steps <= policy.maximum_steps
    assert (
        policy.minimum_guidance_scale
        <= policy.default_guidance_scale
        <= policy.maximum_guidance_scale
    )
