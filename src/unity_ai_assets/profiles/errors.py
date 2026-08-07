"""Profile subsystem exceptions."""

from __future__ import annotations

from typing import Any

from unity_ai_assets.profiles.constants import ProfileErrorCode


class ProfileError(Exception):
    """An expected profile failure with a stable machine-readable code."""

    def __init__(
        self,
        code: ProfileErrorCode | str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = ProfileErrorCode(code)
        self.message = message
        self.details = details or {}
