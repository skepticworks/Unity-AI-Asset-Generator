"""Unit tests for generation manifest parsing and legacy compatibility."""

from __future__ import annotations

import pytest

from unity_ai_assets.core.errors import ManifestSchemaUnsupportedError
from unity_ai_assets.core.version import GENERATION_MANIFEST_SCHEMA_VERSION
from unity_ai_assets.domain.generation_manifest import (
    is_legacy_metadata,
    parse_manifest_payload,
)


def test_legacy_detection() -> None:
    legacy = {
        "generation_id": "11111111-1111-1111-1111-111111111111",
        "prompt": "wall",
        "seed": 1,
    }
    assert is_legacy_metadata(legacy) is True
    versioned = {
        "schema": {"name": "generation-manifest", "version": "1.0"},
        "generation_id": "x",
    }
    assert is_legacy_metadata(versioned) is False


def test_legacy_metadata_parsing() -> None:
    legacy = {
        "generation_id": "11111111-1111-1111-1111-111111111111",
        "created_at_utc": "2026-08-05T18:26:35.172855Z",
        "model_id": "runwayml/stable-diffusion-v1-5",
        "model_revision": None,
        "prompt": "legacy wall",
        "negative_prompt": "photo",
        "seed": 42,
        "width": 64,
        "height": 64,
        "steps": 10,
        "guidance_scale": 7.0,
        "device": "cuda",
        "torch_dtype": "float16",
        "app_version": "0.2.0",
        "elapsed_seconds": 1.5,
        "output_filename": "legacy.png",
    }
    manifest = parse_manifest_payload(legacy)
    assert manifest.schema.version == GENERATION_MANIFEST_SCHEMA_VERSION
    assert manifest.request.prompt == "legacy wall"
    assert manifest.model.family == "unknown"
    assert manifest.runtime.scheduler == "unknown"
    assert manifest.outputs[0].relative_path == "legacy.png"
    assert manifest.outputs[0].sha256 == ""


def test_unknown_manifest_version_rejected() -> None:
    payload = {
        "schema": {"name": "generation-manifest", "version": "99.0"},
        "generation": {},
    }
    with pytest.raises(ManifestSchemaUnsupportedError):
        parse_manifest_payload(payload)


def test_versioned_manifest_roundtrip_keys() -> None:
    payload = {
        "schema": {"name": "generation-manifest", "version": "1.0"},
        "generation": {
            "id": "11111111-1111-1111-1111-111111111111",
            "operation": "text_to_image",
            "asset_type": "texture",
            "status": "completed",
            "created_at_utc": "2026-08-06T15:30:00Z",
            "completed_at_utc": "2026-08-06T15:30:12Z",
            "elapsed_seconds": 12.0,
        },
        "application": {
            "name": "unity-ai-asset-generator",
            "version": "0.3.0",
            "api_major": 1,
        },
        "model": {"id": "fake/model", "revision": None, "family": "sd15"},
        "runtime": {"device": "cpu", "precision": "float32", "scheduler": "pndm"},
        "request": {
            "prompt": "wall",
            "negative_prompt": "",
            "width": 64,
            "height": 64,
            "steps": 5,
            "guidance_scale": 7.0,
            "seed": 1,
            "output_name": "wall",
        },
        "outputs": [
            {
                "kind": "image",
                "format": "png",
                "relative_path": "wall.png",
                "width": 64,
                "height": 64,
                "sha256": "a" * 64,
                "byte_size": 100,
            }
        ],
    }
    manifest = parse_manifest_payload(payload)
    dumped = manifest.to_dict()
    assert dumped["schema"]["version"] == "1.0"
    assert dumped["outputs"][0]["sha256"] == "a" * 64
