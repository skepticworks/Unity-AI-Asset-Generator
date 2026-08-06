"""Ensure fixtures/contracts stay aligned with live backend schemas."""

from __future__ import annotations

import json
from pathlib import Path

from unity_ai_assets.api.schemas.capabilities import CapabilitiesResponse
from unity_ai_assets.api.schemas.generation import ErrorResponse, TextureGenerationResponse
from unity_ai_assets.domain.generation_manifest import parse_manifest_payload

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"


def test_capabilities_fixture_validates() -> None:
    payload = json.loads((FIXTURES / "capabilities.json").read_text(encoding="utf-8"))
    CapabilitiesResponse.model_validate(payload)


def test_generation_response_fixture_validates() -> None:
    payload = json.loads((FIXTURES / "generation_response.json").read_text(encoding="utf-8"))
    TextureGenerationResponse.model_validate(payload)
    assert payload["resources"]["image"].startswith("/api/v1/")
    assert payload["resources"]["manifest"].startswith("/api/v1/")


def test_api_error_fixture_validates() -> None:
    payload = json.loads((FIXTURES / "api_error.json").read_text(encoding="utf-8"))
    ErrorResponse.model_validate(payload)
    assert payload["error"]["code"] == "GENERATION_REQUEST_INVALID"


def test_manifest_fixture_validates() -> None:
    payload = json.loads((FIXTURES / "generation_manifest.json").read_text(encoding="utf-8"))
    manifest = parse_manifest_payload(payload)
    assert manifest.schema.version == "1.0"
    assert manifest.outputs[0].sha256
