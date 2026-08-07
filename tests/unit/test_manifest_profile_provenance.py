"""Manifest profile provenance compatibility tests."""

import json
from pathlib import Path

from unity_ai_assets.domain.generation_manifest import parse_manifest_payload

ROOT = Path(__file__).resolve().parents[2]


def test_manifest_with_provenance_round_trips() -> None:
    payload = json.loads(
        (ROOT / "fixtures" / "profiles" / "manifest_with_provenance.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = parse_manifest_payload(payload)
    assert manifest.profile is not None
    assert manifest.profile.generation_profile_id == "ps1_environment_texture"
    assert manifest.to_dict()["profile"]["profile_origin"] == "builtin"


def test_old_10_manifest_without_profile_defaults_to_none() -> None:
    payload = json.loads(
        (ROOT / "fixtures" / "contracts" / "generation_manifest.json").read_text(encoding="utf-8")
    )
    payload["schema"]["version"] = "1.0"
    payload.pop("profile")
    manifest = parse_manifest_payload(payload)
    assert manifest.to_dict()["profile"]["profile_origin"] == "none"
