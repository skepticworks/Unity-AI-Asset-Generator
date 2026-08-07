"""Syntactic and safety validation for generation profiles."""

from __future__ import annotations

import re
from typing import Any

from unity_ai_assets.domain.enums import is_known_asset_type
from unity_ai_assets.profiles.constants import SEED_STRATEGIES, ProfileErrorCode
from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.models import GenerationProfile, ValidationIssue
from unity_ai_assets.profiles.paths import validate_suggested_output_directory

PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SECRET_KEYS = frozenset(
    {"password", "secret", "token", "api_key", "apikey", "access_key", "private_key"}
)


def validate_profile_id(value: str) -> str:
    if PROFILE_ID_PATTERN.fullmatch(value) is None:
        raise ProfileError(
            ProfileErrorCode.PROFILE_ID_INVALID,
            f"Invalid profile identifier '{value}'.",
        )
    return value


def find_secret_keys(payload: object, prefix: str = "") -> tuple[str, ...]:
    """Return dotted paths for forbidden secret-like keys."""
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in _SECRET_KEYS:
                found.append(path)
            found.extend(find_secret_keys(value, path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(find_secret_keys(value, f"{prefix}[{index}]"))
    return tuple(found)


def validate_generation_profile(profile: GenerationProfile) -> tuple[ValidationIssue, ...]:
    """Validate profile fields and return all non-fatal issues."""
    issues: list[ValidationIssue] = []
    try:
        validate_profile_id(profile.id)
    except ProfileError as exc:
        issues.append(ValidationIssue("schema", exc.code.value, exc.message, "profile.id"))
    if profile.revision < 1:
        issues.append(
            ValidationIssue(
                "schema", "PROFILE_SCHEMA_INVALID", "revision must be positive", "revision"
            )
        )
    if not is_known_asset_type(profile.asset_type):
        issues.append(
            ValidationIssue(
                "schema",
                "ASSET_TYPE_UNSUPPORTED",
                f"Unknown asset type '{profile.asset_type}'.",
                "asset_type",
            )
        )
    defaults = profile.generation_defaults
    if min(defaults.width, defaults.height, defaults.steps) <= 0:
        issues.append(
            ValidationIssue(
                "schema", "PROFILE_SCHEMA_INVALID", "generation defaults must be positive"
            )
        )
    if defaults.seed_strategy not in SEED_STRATEGIES:
        issues.append(
            ValidationIssue(
                "schema", "PROFILE_SCHEMA_INVALID", "invalid seed strategy", "seed_strategy"
            )
        )
    if defaults.seed_strategy == "fixed" and defaults.fixed_seed is None:
        issues.append(
            ValidationIssue(
                "schema", "PROFILE_SCHEMA_INVALID", "fixed seed strategy requires fixed_seed"
            )
        )
    try:
        validate_suggested_output_directory(profile.unity.suggested_output_directory)
    except ProfileError as exc:
        issues.append(
            ValidationIssue(
                "schema", exc.code.value, exc.message, "unity.suggested_output_directory"
            )
        )
    return tuple(issues)


def require_valid_generation_profile(profile: GenerationProfile) -> None:
    issues = validate_generation_profile(profile)
    if issues:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID,
            "; ".join(issue.message for issue in issues),
            {"issues": [issue.code for issue in issues]},
        )


def require_no_secrets(payload: dict[str, Any]) -> None:
    secret_paths = find_secret_keys(payload)
    if secret_paths:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID,
            "Profile payload contains forbidden secret fields.",
            {"fields": list(secret_paths)},
        )
