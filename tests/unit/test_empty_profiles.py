"""Empty passthrough profile tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from unity_ai_assets.profiles.loader import load_builtin_catalog
from unity_ai_assets.profiles.resolver import resolve_generation_profile

ROOT = Path(__file__).resolve().parents[2]
BUILTIN = ROOT / "profiles" / "builtin"

EMPTY_PROFILES = (
    "empty_tileable_texture",
    "empty_standard_texture",
    "empty_sprite",
    "empty_icon",
    "empty_ui",
)


@pytest.mark.parametrize("profile_id", EMPTY_PROFILES)
def test_empty_profiles_pass_subject_through(profile_id: str) -> None:
    catalog = load_builtin_catalog(BUILTIN)
    profile = catalog.generation_profiles[profile_id]
    assert profile.default_modifiers == ()
    assert profile.additional_negative_terms == ()
    negative = catalog.negative_prompt_profiles[profile.negative_prompt_profile_id]
    assert negative.terms == ()
    resolved = resolve_generation_profile(
        profile,
        catalog.prompt_templates[profile.template_id],
        negative,
        subject="test prompt wording",
    )
    assert resolved.prompt == "test prompt wording"
    assert resolved.negative_prompt == ""
