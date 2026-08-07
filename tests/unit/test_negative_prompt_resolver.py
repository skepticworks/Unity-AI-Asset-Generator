"""Negative prompt resolver tests."""

import pytest

from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.models import NegativePromptProfile
from unity_ai_assets.profiles.negative_prompt_resolver import resolve_negative_prompt


def test_exact_deduplication_preserves_order() -> None:
    profile = NegativePromptProfile("base", 1, "Base", "", (), ("text", "logo"))
    assert (
        resolve_negative_prompt(
            profile, additional_terms=("logo", "blur"), user_additions="text, watermark"
        )
        == "text, logo, blur, watermark"
    )


def test_maximum_length_fails_without_truncating() -> None:
    profile = NegativePromptProfile("base", 1, "Base", "", (), ("one", "two"))
    with pytest.raises(ProfileError):
        resolve_negative_prompt(profile, max_length=3)
