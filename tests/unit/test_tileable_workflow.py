"""Tileable profile loading, migration, and generation smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from unity_ai_assets.core.config import Settings, clear_settings_cache
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app
from unity_ai_assets.profiles.loader import load_builtin_catalog, parse_generation_profile
from unity_ai_assets.profiles.migration import migrate_profile_payload
from unity_ai_assets.profiles.resolver import resolve_generation_profile
from unity_ai_assets.profiles.serialize import generation_profile_to_dict

ROOT = Path(__file__).resolve().parents[2]
BUILTIN = ROOT / "profiles" / "builtin"


@pytest.fixture
def tileable_settings(tmp_path: Path) -> Settings:
    clear_settings_cache()
    return Settings(
        model_id="fake/test-model",
        model_family="sd15",
        model_display_name="Fake Test Model",
        device="cpu",
        torch_dtype="float32",
        output_directory=tmp_path / "generated",
        max_width=1024,
        max_height=1024,
        enable_cpu_offload=False,
        local_files_only=True,
        log_level="WARNING",
        app_version="0.6.0-test",
        background_removal_enabled=False,
        preserve_original_image=True,
        seam_inpaint_enabled=True,
    )


@pytest.fixture
def tileable_client(tileable_settings: Settings) -> TestClient:
    backend = FakeImageGenerationBackend(device_name="cpu", model_loaded=False)
    app = create_app(
        settings=tileable_settings,
        backend=backend,
        force_fake_seam_inpaint=True,
    )
    with TestClient(app) as client:
        yield client


def test_builtin_tileable_profile_loads() -> None:
    catalog = load_builtin_catalog(BUILTIN)
    profile = catalog.generation_profiles["ps1_tileable_texture"]
    assert profile.generation_defaults.tileable is True
    assert profile.generation_defaults.apply_seam_correction is False
    assert profile.generation_defaults.palette_reduction_enabled is False
    assert profile.generation_defaults.seam_blend_width == 64
    assert profile.unity.import_profile_id == "ps1_tileable_texture"
    assert "ps1_tileable_texture" in catalog.prompt_templates
    assert "tileable_texture_negative" in catalog.negative_prompt_profiles
    assert catalog.import_profiles["ps1_tileable_texture"].settings["wrap_mode"] == "Repeat"


def test_empty_tileable_profile_uses_subject_as_full_prompt() -> None:
    catalog = load_builtin_catalog(BUILTIN)
    profile = catalog.generation_profiles["empty_tileable_texture"]
    assert profile.generation_defaults.tileable is True
    assert profile.default_modifiers == ()
    assert profile.additional_negative_terms == ()
    assert catalog.negative_prompt_profiles[profile.negative_prompt_profile_id].terms == ()
    resolved = resolve_generation_profile(
        profile,
        catalog.prompt_templates[profile.template_id],
        catalog.negative_prompt_profiles[profile.negative_prompt_profile_id],
        subject="cracked dry mud",
    )
    assert resolved.prompt == "cracked dry mud"
    assert resolved.negative_prompt == ""
    assert resolved.tileable is True


def test_profile_11_migrates_to_12_with_tileable_defaults() -> None:
    source = {
        "schema": {"name": "generation-profile", "version": "1.1"},
        "profile": {
            "id": "user_tex",
            "revision": 1,
            "display_name": "User",
            "description": "d",
            "asset_type": "texture",
            "builtin": False,
            "tags": [],
        },
        "prompt": {
            "template_id": "ps1_environment_texture",
            "template_revision": 1,
            "default_modifiers": [],
        },
        "negative_prompt": {
            "profile_id": "base_ps1_negative",
            "profile_revision": 1,
            "additional_terms": [],
        },
        "generation_defaults": {
            "width": 512,
            "height": 512,
            "steps": 20,
            "guidance_scale": 7.0,
            "seed_strategy": "random",
            "fixed_seed": None,
            "transparency_strategy": "none",
        },
        "unity": {
            "import_profile_id": "ps1_environment_texture",
            "suggested_output_directory": "Assets/Generated/Textures",
            "create_material": True,
        },
    }
    migrated, result = migrate_profile_payload(source)
    assert result.migrated
    assert "1.1->1.2" in result.steps
    profile = parse_generation_profile(migrated)
    assert profile.schema_version == "1.2"
    assert profile.generation_defaults.tileable is False
    assert profile.generation_defaults.palette_color_count == 16
    round_trip = generation_profile_to_dict(profile)
    assert round_trip["generation_defaults"]["tileable"] is False


def test_capabilities_advertise_tileable_processing(tileable_client: TestClient) -> None:
    payload = tileable_client.get("/api/v1/capabilities").json()
    assert payload["schemas"]["capabilities"] == "1.4"
    tileable = payload["operations"]["text_to_image"]["processing"]["tileable"]
    assert tileable["available"] is True
    assert tileable["seam_analysis"] is True
    assert tileable["seam_correction"] is True
    assert tileable["palette_reduction"] is True
    assert tileable["ai_inpaint_available"] is True
    assert tileable["target_size"] == 512
    assert tileable["circular_offset_px"] == 256
    assert tileable["protected_border_px"] == 4
    assert tileable["seam_blend_width"]["default"] == 64
    assert tileable["seam_blend_width"]["minimum"] == 8
    assert tileable["seam_blend_width"]["maximum"] == 128


def test_tileable_generation_with_optional_correction(tileable_client: TestClient) -> None:
    response = tileable_client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "seamless rusted metal plate",
            "width": 512,
            "height": 512,
            "steps": 5,
            "seed": 3,
            "output_name": "tile_metal",
            "asset_type": "texture",
            "tileable": True,
            "apply_seam_correction": True,
            "seam_blend_width": 64,
            "palette_reduction_enabled": True,
            "palette_color_count": 8,
            "unity_import_profile_id": "ps1_tileable_texture",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    generation_id = body["generation_id"]
    image_bytes = tileable_client.get(f"/api/v1/generations/{generation_id}/image").content
    image = Image.open(__import__("io").BytesIO(image_bytes))
    assert image.size == (512, 512)

    manifest = tileable_client.get(f"/api/v1/generations/{generation_id}/manifest").json()
    assert manifest["schema"]["version"] == "1.5"
    assert manifest["request"]["tileable"] is True
    assert manifest["request"]["apply_seam_correction"] is True
    processing = manifest["processing"]
    assert processing["tileable"] is True
    assert processing["seam_correction_applied"] is True
    assert processing["palette_reduction_applied"] is True
    assert processing["seam_inpaint_implementation"] == "fake:neighbor_fill"
    assert processing["horizontal_wrap_discontinuity"] is not None
    assert processing["vertical_wrap_discontinuity"] is not None
    assert processing["original_relative_path"] == "tile_metal.original.png"
    kinds = {item["kind"] for item in manifest["outputs"]}
    assert "image" in kinds
    assert "original_image" in kinds


def test_seam_correction_requires_512(tileable_client: TestClient) -> None:
    response = tileable_client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "metal",
            "width": 64,
            "height": 64,
            "steps": 5,
            "seed": 1,
            "output_name": "too_small",
            "asset_type": "texture",
            "tileable": True,
            "apply_seam_correction": True,
            "seam_blend_width": 64,
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "GENERATION_REQUEST_INVALID"


def test_seam_inpaint_unavailable_rejects_correction(tmp_path: Path) -> None:
    clear_settings_cache()
    settings = Settings(
        model_id="fake/test-model",
        model_family="sd15",
        device="cpu",
        torch_dtype="float32",
        output_directory=tmp_path / "generated",
        local_files_only=True,
        log_level="WARNING",
        app_version="0.6.0-test",
        background_removal_enabled=False,
        seam_inpaint_enabled=False,
    )
    backend = FakeImageGenerationBackend(device_name="cpu", model_loaded=False)
    app = create_app(settings=settings, backend=backend, force_fake_seam_inpaint=False)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/generations/textures",
            json={
                "prompt": "metal",
                "width": 512,
                "height": 512,
                "steps": 5,
                "seed": 1,
                "output_name": "no_inpaint",
                "asset_type": "texture",
                "tileable": True,
                "apply_seam_correction": True,
                "seam_blend_width": 64,
            },
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SEAM_INPAINT_UNAVAILABLE"
