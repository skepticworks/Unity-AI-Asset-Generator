"""Generation profile loader and serialization tests."""

import json
from pathlib import Path

from unity_ai_assets.profiles.loader import load_json_file, parse_generation_profile
from unity_ai_assets.profiles.serialize import dumps_generation_profile

ROOT = Path(__file__).resolve().parents[2]


def test_user_profile_round_trip() -> None:
    payload = load_json_file(ROOT / "fixtures" / "profiles" / "user_profile.json")
    profile = parse_generation_profile(payload)
    assert profile.id == "user_stone_texture"
    assert profile.builtin is False
    assert parse_generation_profile(json.loads(dumps_generation_profile(profile))) == profile
