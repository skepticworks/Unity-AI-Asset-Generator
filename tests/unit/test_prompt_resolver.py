"""Safe prompt resolver tests."""

import pytest

from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.models import PromptTemplate
from unity_ai_assets.profiles.prompt_resolver import resolve_prompt


def _template(pattern: str) -> PromptTemplate:
    return PromptTemplate(
        "test",
        1,
        "Test",
        "",
        "texture",
        pattern,
        ("subject", "style_modifiers", "asset_type"),
        ("subject",),
    )


def test_resolves_modifiers_deterministically_and_cleans_empty_separator() -> None:
    template = _template("{subject}, {style_modifiers}")
    assert resolve_prompt(template, subject="wall", style_modifiers=["old", "stone"]) == (
        "wall, old, stone"
    )
    assert resolve_prompt(template, subject="wall") == "wall"


def test_required_subject_and_unknown_placeholders_fail() -> None:
    with pytest.raises(ProfileError, match="subject"):
        resolve_prompt(_template("{subject}"), subject=" ")
    with pytest.raises(ProfileError, match="unknown"):
        resolve_prompt(_template("{subject}, {unsafe}"), subject="wall")
