"""Negative-prompt assembly with stable exact deduplication."""

from __future__ import annotations

from collections.abc import Iterable

from unity_ai_assets.profiles.constants import CompatibilityReasonCode, ProfileErrorCode
from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.models import NegativePromptProfile


def _terms(value: str | Iterable[str]) -> Iterable[str]:
    if isinstance(value, str):
        return value.split(",")
    return value


def resolve_negative_prompt(
    profile: NegativePromptProfile,
    *,
    additional_terms: Iterable[str] = (),
    user_additions: str | Iterable[str] = (),
    max_length: int | None = None,
) -> str:
    """Join terms in source order and remove exact duplicates."""
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in (*profile.terms, *tuple(additional_terms), *_terms(user_additions)):
        term = raw.strip()
        if term and term not in seen:
            seen.add(term)
            ordered.append(term)
    resolved = ", ".join(ordered)
    if max_length is not None and len(resolved) > max_length:
        raise ProfileError(
            ProfileErrorCode.PROFILE_INCOMPATIBLE,
            f"Resolved negative prompt exceeds maximum length {max_length}.",
            {
                "code": CompatibilityReasonCode.NEGATIVE_PROMPT_TOO_LONG.value,
                "length": len(resolved),
            },
        )
    return resolved


build_negative_prompt = resolve_negative_prompt
