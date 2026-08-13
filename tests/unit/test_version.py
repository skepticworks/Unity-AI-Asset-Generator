"""Unit tests for version constants and application version resolution."""

from __future__ import annotations

from unity_ai_assets.core import version as version_module
from unity_ai_assets.core.version import (
    API_MAJOR_VERSION,
    API_MINOR_VERSION,
    APPLICATION_NAME,
    APPLICATION_VERSION,
    APPLICATION_VERSION_FALLBACK,
    CAPABILITIES_SCHEMA_VERSION,
    GENERATION_MANIFEST_SCHEMA_VERSION,
    resolve_application_version,
)


def test_api_version_constants() -> None:
    assert API_MAJOR_VERSION == 1
    assert API_MINOR_VERSION == 3


def test_schema_versions() -> None:
    assert CAPABILITIES_SCHEMA_VERSION == "1.5"
    assert GENERATION_MANIFEST_SCHEMA_VERSION == "1.5"


def test_application_identity() -> None:
    assert APPLICATION_NAME == "unity-ai-asset-generator"
    assert APPLICATION_VERSION_FALLBACK == "0.9.0"
    assert APPLICATION_VERSION
    resolved = resolve_application_version()
    assert resolved == APPLICATION_VERSION
    assert resolved == APPLICATION_VERSION_FALLBACK or resolved.count(".") >= 1


def test_version_module_is_single_source() -> None:
    assert version_module.CAPABILITIES_SCHEMA_VERSION == "1.5"
    assert version_module.GENERATION_MANIFEST_SCHEMA_VERSION == "1.5"
