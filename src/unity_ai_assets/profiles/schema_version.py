"""Profile schema version parsing and compatibility."""

from __future__ import annotations

import re

from unity_ai_assets.profiles.constants import ProfileErrorCode
from unity_ai_assets.profiles.errors import ProfileError

_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_schema_version(value: str) -> tuple[int, int]:
    """Parse a strict major.minor schema version."""
    match = _VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID,
            f"Invalid schema version '{value}'; expected major.minor.",
        )
    return int(match.group(1)), int(match.group(2))


def is_compatible(current: str, declared: str) -> bool:
    """Return true when declared uses the supported current major version."""
    current_major, _ = parse_schema_version(current)
    declared_major, _ = parse_schema_version(declared)
    if declared_major != current_major:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_UNSUPPORTED,
            f"Unsupported schema version '{declared}'; current is '{current}'.",
        )
    return True
