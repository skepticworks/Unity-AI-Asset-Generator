"""Profile capability evaluation tests."""

from pathlib import Path

from unity_ai_assets.profiles.compatibility import evaluate_profile_compatibility
from unity_ai_assets.profiles.loader import load_json_file, parse_generation_profile

ROOT = Path(__file__).resolve().parents[2]


def test_incompatible_profile_reports_all_relevant_reasons() -> None:
    profile = parse_generation_profile(
        load_json_file(ROOT / "fixtures" / "profiles" / "incompatible_sprite.json")
    )
    result = evaluate_profile_compatibility(
        profile,
        supported_asset_types=["texture"],
        negative_prompt_supported=True,
        maximum_width=1024,
        maximum_height=1024,
        width_multiple=8,
        height_multiple=8,
        maximum_steps=50,
        maximum_seed=2**32 - 1,
        import_profile_ids=["ps1_sprite"],
        template_ids=["ps1_character_sprite"],
        negative_ids=["sprite_negative"],
    )
    codes = {issue.code for issue in result.issues}
    assert not result.compatible
    assert {"ASSET_TYPE_UNSUPPORTED", "WIDTH_MULTIPLE_INVALID", "STEPS_OUT_OF_RANGE"} <= codes
