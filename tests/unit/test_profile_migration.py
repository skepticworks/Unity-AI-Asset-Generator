"""Generation profile migration tests."""

from pathlib import Path

from unity_ai_assets.profiles.loader import load_json_file, parse_generation_profile
from unity_ai_assets.profiles.migration import migrate_profile_payload

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_09_migrates_in_memory() -> None:
    source = load_json_file(ROOT / "fixtures" / "profiles" / "migrated_0_9.json")
    migrated, result = migrate_profile_payload(source)
    profile = parse_generation_profile(migrated)
    assert result.migrated
    assert result.steps == ("0.9->1.0", "1.0->1.1")
    assert migrated["schema"]["version"] == "1.1"
    assert profile.revision == 1
    assert profile.generation_defaults.seed_strategy == "random"
    assert source["schema"]["version"] == "0.9"
