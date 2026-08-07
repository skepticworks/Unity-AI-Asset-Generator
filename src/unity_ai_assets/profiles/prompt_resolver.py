"""Deterministic, safe prompt-template substitution."""

from __future__ import annotations

import re
from collections.abc import Sequence

from unity_ai_assets.profiles.constants import (
    KNOWN_PLACEHOLDERS,
    CompatibilityReasonCode,
    ProfileErrorCode,
)
from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.models import PromptTemplate

_PLACEHOLDER_PATTERN = re.compile(r"\{([a-z_]+)\}")


def extract_placeholders(pattern: str) -> frozenset[str]:
    """Extract supported placeholder-shaped tokens from a pattern."""
    return frozenset(_PLACEHOLDER_PATTERN.findall(pattern))


def resolve_prompt(
    template: PromptTemplate,
    *,
    subject: str,
    style_modifiers: Sequence[str] = (),
    asset_type: str | None = None,
    additional_prompt: str = "",
    max_length: int | None = None,
) -> str:
    """Resolve a template without allowing arbitrary format expressions."""
    present = extract_placeholders(template.pattern)
    declared = frozenset(template.placeholders)
    unknown = present - declared | present - KNOWN_PLACEHOLDERS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID,
            f"Prompt template contains unknown placeholders: {names}.",
            {"placeholders": sorted(unknown)},
        )
    required = frozenset(template.required_placeholders)
    if "subject" in required and not subject.strip():
        raise ProfileError(
            ProfileErrorCode.PROFILE_REFERENCE_INVALID,
            "A non-empty subject is required by this prompt template.",
        )

    modifiers = ", ".join(item.strip() for item in style_modifiers if item.strip())
    replacements = {
        "subject": subject.strip(),
        "style_modifiers": modifiers,
        "asset_type": (asset_type or template.asset_type).strip(),
    }
    resolved = template.pattern
    for placeholder in sorted(present):
        resolved = resolved.replace(f"{{{placeholder}}}", replacements[placeholder])

    # Normalize separators left by optional empty values, without changing word order.
    resolved = re.sub(r"\s*,\s*,+", ", ", resolved)
    resolved = re.sub(r",\s*$", "", resolved)
    resolved = re.sub(r"[ \t]{2,}", " ", resolved).strip(" ,")
    if additional_prompt.strip():
        resolved = (
            f"{resolved}, {additional_prompt.strip()}" if resolved else additional_prompt.strip()
        )
    if max_length is not None and len(resolved) > max_length:
        raise ProfileError(
            ProfileErrorCode.PROFILE_INCOMPATIBLE,
            f"Resolved prompt exceeds maximum length {max_length}.",
            {"code": CompatibilityReasonCode.PROMPT_TOO_LONG.value, "length": len(resolved)},
        )
    return resolved


resolve_prompt_template = resolve_prompt
