#!/usr/bin/env python3
"""Validate builtin profile registries and their Unity package mirror."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from unity_ai_assets.domain.enums import is_known_asset_type  # noqa: E402
from unity_ai_assets.profiles.constants import KNOWN_PLACEHOLDERS  # noqa: E402
from unity_ai_assets.profiles.errors import ProfileError  # noqa: E402
from unity_ai_assets.profiles.paths import validate_suggested_output_directory  # noqa: E402
from unity_ai_assets.profiles.prompt_resolver import extract_placeholders  # noqa: E402
from unity_ai_assets.profiles.registry import ProfileRegistry  # noqa: E402

CANONICAL = ROOT / "profiles" / "builtin"
UNITY_MIRROR = ROOT / "unity-package" / "Editor" / "Profiles" / "Builtin"


def _normalized(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_parity() -> None:
    canonical = sorted(path.relative_to(CANONICAL) for path in CANONICAL.rglob("*.json"))
    mirrored = sorted(path.relative_to(UNITY_MIRROR) for path in UNITY_MIRROR.rglob("*.json"))
    if canonical != mirrored:
        raise ValueError("Canonical and Unity builtin profile file lists differ.")
    for relative in canonical:
        if _normalized(CANONICAL / relative) != _normalized(UNITY_MIRROR / relative):
            raise ValueError(f"Builtin profile mirror differs: {relative}.")


def main() -> None:
    try:
        registry = ProfileRegistry(CANONICAL)
        for asset_type in registry.catalog.asset_types.values():
            if not is_known_asset_type(asset_type.id):
                raise ValueError(f"Unknown asset type '{asset_type.id}'.")
            validate_suggested_output_directory(asset_type.suggested_output_directory)
        for template in registry.prompt_templates.values():
            placeholders = extract_placeholders(template.pattern)
            undeclared = placeholders - frozenset(template.placeholders)
            unknown = placeholders - KNOWN_PLACEHOLDERS
            if undeclared or unknown:
                raise ValueError(f"Invalid placeholders in template '{template.id}'.")
            if not frozenset(template.required_placeholders) <= placeholders:
                raise ValueError(f"Missing required placeholder in template '{template.id}'.")
        validate_parity()
    except (OSError, ValueError, ProfileError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        "Builtin profiles OK: "
        f"{len(registry.generation_profiles)} generation, "
        f"{len(registry.prompt_templates)} templates, "
        f"{len(registry.negative_prompt_profiles)} negative, "
        f"{len(registry.import_profiles)} import."
    )


if __name__ == "__main__":
    main()
