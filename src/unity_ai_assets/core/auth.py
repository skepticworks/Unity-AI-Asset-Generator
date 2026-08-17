"""Configurable authentication for network-accessible API deployments."""

from __future__ import annotations

import secrets

from fastapi import Request

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import AuthenticationRequiredError


class ApiKeyAuthenticator:
    """Authenticate bearer tokens without logging supplied credentials."""

    def __init__(self, settings: Settings) -> None:
        self._mode = settings.authentication_mode
        self._api_key = settings.api_key

    def authenticate(self, request: Request) -> str:
        """Return an anonymous or API-key client identifier."""
        if self._mode == "disabled":
            return "local"
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or self._api_key is None:
            raise AuthenticationRequiredError()
        if not secrets.compare_digest(token, self._api_key):
            raise AuthenticationRequiredError()
        return "api-key"
