"""Builtin registry tests."""

from pathlib import Path

from unity_ai_assets.profiles.registry import ProfileRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_builtin_registry_loads_and_resolves_references() -> None:
    registry = ProfileRegistry(ROOT / "profiles" / "builtin")
    profile = registry.get_generation_profile("ps1_environment_texture")
    assert profile.builtin
    assert registry.get_prompt_template(profile.template_id).revision == profile.template_revision
    assert registry.filter_by_asset_type("texture")
