"""Explicit in-memory generation-profile migration framework."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, cast

from unity_ai_assets.profiles.constants import GENERATION_PROFILE_SCHEMA_VERSION, ProfileErrorCode
from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.models import MigrationResult
from unity_ai_assets.profiles.schema_version import parse_schema_version


class MigrationStep(Protocol):
    """One deterministic profile payload migration."""

    source_version: str
    target_version: str

    def migrate(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class Legacy09To10Migration:
    source_version = "0.9"
    target_version = "1.0"

    def migrate(self, payload: dict[str, Any]) -> dict[str, Any]:
        migrated = deepcopy(payload)
        schema = cast(dict[str, Any], migrated["schema"])
        schema["version"] = self.target_version
        profile = cast(dict[str, Any], migrated["profile"])
        if "revision" not in profile and "profile_version" in profile:
            profile["revision"] = profile.pop("profile_version")
        elif "revision" not in profile and "profile_version" in migrated:
            profile["revision"] = migrated.pop("profile_version")
        defaults = cast(dict[str, Any], migrated["generation_defaults"])
        defaults.setdefault("seed_strategy", "random")
        defaults.setdefault("fixed_seed", None)
        return migrated


class Profile10To11Migration:
    """Additive Milestone 5 fields for sprite/icon processing defaults."""

    source_version = "1.0"
    target_version = "1.1"

    def migrate(self, payload: dict[str, Any]) -> dict[str, Any]:
        migrated = deepcopy(payload)
        schema = cast(dict[str, Any], migrated["schema"])
        schema["version"] = self.target_version
        defaults = cast(dict[str, Any], migrated["generation_defaults"])
        defaults.setdefault("transparency_strategy", "none")
        defaults.setdefault("alpha_threshold", 16)
        defaults.setdefault("alpha_feather", 0)
        defaults.setdefault("remove_near_transparent", True)
        defaults.setdefault("zero_rgb_when_transparent", True)
        defaults.setdefault("pixels_per_unit", None)
        defaults.setdefault("pivot_mode", None)
        defaults.setdefault("custom_pivot_x", None)
        defaults.setdefault("custom_pivot_y", None)
        defaults.setdefault("atlas_hint", None)
        unity = cast(dict[str, Any], migrated["unity"])
        unity.setdefault("pixels_per_unit", None)
        unity.setdefault("pivot_mode", None)
        unity.setdefault("custom_pivot_x", None)
        unity.setdefault("custom_pivot_y", None)
        unity.setdefault("atlas_hint", None)
        return migrated


class Profile11To12Migration:
    """Additive Milestone 6 fields for tileable texture workflow defaults."""

    source_version = "1.1"
    target_version = "1.2"

    def migrate(self, payload: dict[str, Any]) -> dict[str, Any]:
        migrated = deepcopy(payload)
        schema = cast(dict[str, Any], migrated["schema"])
        schema["version"] = self.target_version
        defaults = cast(dict[str, Any], migrated["generation_defaults"])
        defaults.setdefault("tileable", False)
        defaults.setdefault("apply_seam_correction", False)
        defaults.setdefault("seam_blend_width", 64)
        defaults.setdefault("palette_reduction_enabled", False)
        defaults.setdefault("palette_color_count", 16)
        return migrated


_MIGRATIONS: tuple[MigrationStep, ...] = (
    Legacy09To10Migration(),
    Profile10To11Migration(),
    Profile11To12Migration(),
)


def migrate_profile_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], MigrationResult]:
    """Migrate a payload in memory only; never writes the source file."""
    try:
        schema = payload["schema"]
        if not isinstance(schema, dict) or not isinstance(schema.get("version"), str):
            raise KeyError("schema.version")
        source = str(schema["version"])
        source_major, _ = parse_schema_version(source)
        target_major, _ = parse_schema_version(GENERATION_PROFILE_SCHEMA_VERSION)
    except (KeyError, TypeError) as exc:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID, "Profile schema version is missing."
        ) from exc
    if source_major > target_major:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_UNSUPPORTED,
            f"Future profile schema version '{source}' is unsupported.",
        )
    if source == GENERATION_PROFILE_SCHEMA_VERSION:
        return deepcopy(payload), MigrationResult(False, source, source)

    current = deepcopy(payload)
    version = source
    applied: list[str] = []
    while version != GENERATION_PROFILE_SCHEMA_VERSION:
        step = next((item for item in _MIGRATIONS if item.source_version == version), None)
        if step is None:
            raise ProfileError(
                ProfileErrorCode.PROFILE_MIGRATION_FAILED,
                f"No migration path from profile schema '{version}'.",
            )
        try:
            current = step.migrate(current)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProfileError(
                ProfileErrorCode.PROFILE_MIGRATION_FAILED,
                f"Migration from '{step.source_version}' failed.",
            ) from exc
        applied.append(f"{step.source_version}->{step.target_version}")
        version = step.target_version
    return current, MigrationResult(True, source, version, tuple(applied))
