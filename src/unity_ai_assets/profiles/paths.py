"""Unity project-relative profile path validation."""

from __future__ import annotations

import re

from unity_ai_assets.profiles.constants import ProfileErrorCode
from unity_ai_assets.profiles.errors import ProfileError

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def validate_suggested_output_directory(value: str) -> str:
    """Require a safe, forward-slash Unity Assets path."""
    path = value.strip()
    parts = path.replace("\\", "/").split("/")
    if (
        not path.startswith("Assets/")
        or path.startswith("/")
        or _WINDOWS_ABSOLUTE.match(path)
        or "\\" in path
        or ".." in parts
        or any(not part for part in parts)
    ):
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID,
            "suggested_output_directory must be a relative Assets/... path without traversal.",
            {"path": value},
        )
    return path
