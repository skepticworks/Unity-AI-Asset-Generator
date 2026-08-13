#!/usr/bin/env python3
"""Validate canonical contract fixtures against backend schemas and Unity field expectations.

Usage:
    python scripts/validate_contract_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "contracts"
sys.path.insert(0, str(ROOT / "src"))

from unity_ai_assets.api.schemas.capabilities import CapabilitiesResponse  # noqa: E402
from unity_ai_assets.api.schemas.generation import (  # noqa: E402
    ErrorResponse,
    TextureGenerationResponse,
)
from unity_ai_assets.domain.generation_manifest import parse_manifest_payload  # noqa: E402

# Unity wire field names expected in each fixture (snake_case JSON keys).
REQUIRED_CAPABILITY_PATHS = [
    ("api", "major"),
    ("api", "minor"),
    ("application", "name"),
    ("application", "version"),
    ("schemas", "capabilities"),
    ("schemas", "generation_manifest"),
    ("runtime", "configured_device"),
    ("runtime", "resolved_device"),
    ("runtime", "configured_precision"),
    ("runtime", "resolved_precision"),
    ("runtime", "model_loaded"),
    ("model", "id"),
    ("model", "family"),
    ("operations", "text_to_image", "supported"),
    ("operations", "text_to_image", "dimensions", "minimum_width"),
    ("operations", "text_to_image", "dimensions", "maximum_width"),
    ("operations", "text_to_image", "dimensions", "width_multiple"),
    ("operations", "text_to_image", "steps", "minimum"),
    ("operations", "text_to_image", "steps", "maximum"),
    ("operations", "text_to_image", "guidance_scale", "minimum"),
    ("operations", "text_to_image", "guidance_scale", "maximum"),
    ("operations", "text_to_image", "seed", "minimum"),
    ("operations", "text_to_image", "seed", "maximum"),
    ("operations", "text_to_image", "prompt", "maximum_length"),
    ("operations", "text_to_image", "negative_prompt", "supported"),
    ("operations", "text_to_image", "output_name", "maximum_length"),
    ("operations", "text_to_image", "schedulers", "selection_supported"),
    ("operations", "image_to_image", "supported"),
    ("operations", "image_to_image", "denoising_strength", "minimum"),
    ("operations", "image_to_image", "denoising_strength", "maximum"),
    ("operations", "image_to_image", "denoising_strength", "default"),
    ("operations", "image_to_image", "source_image", "supported_formats"),
    ("operations", "image_to_image", "source_image", "maximum_byte_size"),
    ("operations", "inpainting", "supported"),
    ("operations", "inpainting", "denoising_strength", "minimum"),
    ("operations", "inpainting", "denoising_strength", "maximum"),
    ("operations", "inpainting", "source_image", "supported_formats"),
    ("operations", "inpainting", "mask_image", "supported_formats"),
    ("operations", "inpainting", "mask_image", "convention"),
    ("operations", "inpainting", "mask_image", "white_means"),
    ("operations", "inpainting", "mask_image", "black_means"),
    ("operations", "inpainting", "mask_image", "must_match_source_dimensions"),
    ("precision", "user_selectable"),
    ("limits", "maximum_concurrent_generations"),
    ("jobs", "supported"),
    ("batches", "supported"),
    ("batches", "maximum_jobs"),
]

REQUIRED_GENERATION_RESPONSE_KEYS = [
    "generation_id",
    "status",
    "operation",
    "asset_type",
    "seed",
    "width",
    "height",
    "elapsed_seconds",
    "resources",
    "schema_versions",
]

REQUIRED_MANIFEST_PATHS = [
    ("schema", "name"),
    ("schema", "version"),
    ("generation", "id"),
    ("generation", "operation"),
    ("generation", "asset_type"),
    ("generation", "status"),
    ("application", "name"),
    ("application", "version"),
    ("application", "api_major"),
    ("model", "id"),
    ("model", "family"),
    ("runtime", "device"),
    ("runtime", "precision"),
    ("runtime", "scheduler"),
    ("request", "prompt"),
    ("request", "seed"),
    ("profile", "profile_origin"),
    ("outputs",),
]


def _has_path(payload: object, path: tuple[str, ...]) -> bool:
    current: object = payload
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not FIXTURES.is_dir():
        _fail(f"Missing fixtures directory: {FIXTURES}")

    caps_path = FIXTURES / "capabilities.json"
    gen_path = FIXTURES / "generation_response.json"
    err_path = FIXTURES / "api_error.json"
    man_path = FIXTURES / "generation_manifest.json"

    for path in (caps_path, gen_path, err_path, man_path):
        if not path.is_file():
            _fail(f"Missing fixture: {path}")

    caps = json.loads(caps_path.read_text(encoding="utf-8"))
    try:
        CapabilitiesResponse.model_validate(caps)
    except ValidationError as exc:
        _fail(f"capabilities.json schema validation failed: {exc}")
    for path in REQUIRED_CAPABILITY_PATHS:
        if not _has_path(caps, path):
            _fail(f"capabilities.json missing Unity-required path: {'.'.join(path)}")

    gen = json.loads(gen_path.read_text(encoding="utf-8"))
    try:
        TextureGenerationResponse.model_validate(gen)
    except ValidationError as exc:
        _fail(f"generation_response.json schema validation failed: {exc}")
    for key in REQUIRED_GENERATION_RESPONSE_KEYS:
        if key not in gen:
            _fail(f"generation_response.json missing key: {key}")
    if "image" not in gen.get("resources", {}):
        _fail("generation_response.json resources.image missing")
    if "manifest" not in gen.get("resources", {}):
        _fail("generation_response.json resources.manifest missing")
    # Primary contract must not require absolute filesystem paths.
    for url_key in ("image", "manifest"):
        value = gen["resources"][url_key]
        if not str(value).startswith("/api/"):
            _fail(f"resources.{url_key} must be an API-relative URL")

    err = json.loads(err_path.read_text(encoding="utf-8"))
    try:
        ErrorResponse.model_validate(err)
    except ValidationError as exc:
        _fail(f"api_error.json schema validation failed: {exc}")
    if "code" not in err.get("error", {}):
        _fail("api_error.json missing error.code")
    if "request_id" not in err.get("error", {}):
        _fail("api_error.json missing error.request_id")

    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    try:
        parse_manifest_payload(manifest)
    except Exception as exc:  # noqa: BLE001
        _fail(f"generation_manifest.json parse failed: {exc}")
    for path in REQUIRED_MANIFEST_PATHS:
        if path == ("outputs",):
            if not isinstance(manifest.get("outputs"), list) or not manifest["outputs"]:
                _fail("generation_manifest.json outputs missing")
            continue
        if not _has_path(manifest, path):
            _fail(f"generation_manifest.json missing path: {'.'.join(path)}")
    relative = manifest["outputs"][0].get("relative_path", "")
    if relative.startswith("/") or ":" in relative or ".." in relative:
        _fail("manifest output relative_path must be relative and safe")

    # Detect obvious absolute path leakage in public fixtures.
    serialized = json.dumps({"caps": caps, "gen": gen, "err": err, "man": manifest})
    if "C:\\\\Users" in serialized or "/home/" in serialized:
        _fail("fixtures appear to contain machine-specific absolute paths")

    print("Contract fixtures OK:")
    print(f"  - {caps_path.relative_to(ROOT)}")
    print(f"  - {gen_path.relative_to(ROOT)}")
    print(f"  - {err_path.relative_to(ROOT)}")
    print(f"  - {man_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
