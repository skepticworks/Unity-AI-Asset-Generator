"""Sprite/icon generation, transparency, and capability tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from unity_ai_assets.core.config import Settings, clear_settings_cache
from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app
from unity_ai_assets.profiles.compatibility import evaluate_profile_compatibility
from unity_ai_assets.profiles.loader import load_builtin_catalog

ROOT = Path(__file__).resolve().parents[2]
BUILTIN = ROOT / "profiles" / "builtin"


@pytest.fixture
def sprite_settings(tmp_path: Path) -> Settings:
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
        app_version="0.5.0-test",
        background_removal_enabled=True,
        background_removal_backend="fake",
        preserve_original_image=True,
    )


@pytest.fixture
def sprite_client(sprite_settings: Settings) -> TestClient:
    backend = FakeImageGenerationBackend(device_name="cpu", model_loaded=False)
    app = create_app(
        settings=sprite_settings,
        backend=backend,
        force_fake_background_removal=True,
    )
    with TestClient(app) as client:
        yield client


def test_capabilities_report_sprite_icon_and_processing(sprite_client: TestClient) -> None:
    payload = sprite_client.get("/api/v1/capabilities").json()
    assert payload["schemas"]["capabilities"] == "1.2"
    t2i = payload["operations"]["text_to_image"]
    assert "sprite" in t2i["asset_types"]
    assert "icon" in t2i["asset_types"]
    processing = t2i["processing"]
    assert "none" in processing["transparency_strategies"]
    assert "background_removal" in processing["transparency_strategies"]
    assert processing["background_removal"]["available"] is True
    assert processing["background_removal"]["produces_native_alpha"] is False
    assert processing["alpha_cleanup"]["available"] is True
    assert processing["sprite_import"]["single_sprite_only"] is True


def test_sprite_generation_with_background_removal(sprite_client: TestClient) -> None:
    response = sprite_client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "ps1 hero character",
            "width": 64,
            "height": 64,
            "steps": 5,
            "seed": 7,
            "output_name": "hero_sprite",
            "asset_type": "sprite",
            "transparency_strategy": "background_removal",
            "alpha_threshold": 16,
            "alpha_feather": 0,
            "pixels_per_unit": 100,
            "pivot_mode": "bottom_center",
            "atlas_hint": "characters",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["asset_type"] == "sprite"
    generation_id = body["generation_id"]

    image_bytes = sprite_client.get(f"/api/v1/generations/{generation_id}/image").content
    image = Image.open(__import__("io").BytesIO(image_bytes))
    assert image.mode == "RGBA"
    assert image.size == (64, 64)

    manifest = sprite_client.get(f"/api/v1/generations/{generation_id}/manifest").json()
    assert manifest["schema"]["version"] == "1.3"
    assert manifest["request"]["transparency_strategy"] == "background_removal"
    assert manifest["request"]["pixels_per_unit"] == 100
    assert manifest["request"]["pivot_mode"] == "bottom_center"
    assert manifest["request"]["atlas_hint"] == "characters"
    processing = manifest["processing"]
    assert processing["background_removal_applied"] is True
    assert processing["alpha_cleanup_applied"] is True
    assert processing["final_relative_path"] == "hero_sprite.png"
    assert processing["original_relative_path"] == "hero_sprite.original.png"
    kinds = {item["kind"] for item in manifest["outputs"]}
    assert "image" in kinds
    assert "original_image" in kinds
    final = next(item for item in manifest["outputs"] if item["kind"] == "image")
    assert final["sha256"]
    assert final["byte_size"] > 0


def test_icon_generation_center_pivot(sprite_client: TestClient) -> None:
    response = sprite_client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "ps1 potion icon",
            "width": 64,
            "height": 64,
            "steps": 3,
            "seed": 3,
            "output_name": "potion",
            "asset_type": "icon",
            "transparency_strategy": "background_removal",
            "pixels_per_unit": 64,
            "pivot_mode": "center",
            "atlas_hint": "items",
        },
    )
    assert response.status_code == 200, response.text
    manifest = sprite_client.get(
        f"/api/v1/generations/{response.json()['generation_id']}/manifest"
    ).json()
    assert manifest["generation"]["asset_type"] == "icon"
    assert manifest["request"]["pivot_mode"] == "center"


def test_background_removal_unavailable_when_disabled(tmp_path: Path) -> None:
    clear_settings_cache()
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        torch_dtype="float32",
        output_directory=tmp_path / "generated",
        background_removal_enabled=False,
        app_version="0.5.0-test",
    )
    app = create_app(
        settings=settings,
        backend=FakeImageGenerationBackend(model_loaded=False),
        force_fake_background_removal=False,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/generations/textures",
            json={
                "prompt": "sprite",
                "width": 64,
                "height": 64,
                "steps": 2,
                "asset_type": "sprite",
                "transparency_strategy": "background_removal",
                "pixels_per_unit": 100,
                "pivot_mode": "center",
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE.value


def test_invalid_pivot_rejected(sprite_client: TestClient) -> None:
    response = sprite_client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "sprite",
            "width": 64,
            "height": 64,
            "steps": 2,
            "asset_type": "sprite",
            "transparency_strategy": "none",
            "pixels_per_unit": 100,
            "pivot_mode": "custom",
        },
    )
    assert response.status_code == 422


def test_invalid_pixels_per_unit_rejected(sprite_client: TestClient) -> None:
    response = sprite_client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "sprite",
            "width": 64,
            "height": 64,
            "steps": 2,
            "asset_type": "sprite",
            "transparency_strategy": "none",
            "pixels_per_unit": -1,
            "pivot_mode": "center",
        },
    )
    assert response.status_code == 422


def test_texture_soft_ignores_sprite_fields(sprite_client: TestClient) -> None:
    response = sprite_client.post(
        "/api/v1/generations/textures",
        json={
            "prompt": "wall",
            "width": 64,
            "height": 64,
            "steps": 2,
            "seed": 1,
            "output_name": "wall_tex",
            "asset_type": "texture",
            "pixels_per_unit": 100,
            "pivot_mode": "center",
            "atlas_hint": "ignored",
        },
    )
    assert response.status_code == 200, response.text
    generation_id = response.json()["generation_id"]
    manifest = sprite_client.get(f"/api/v1/generations/{generation_id}/manifest").json()
    assert "pixels_per_unit" not in manifest["request"]
    assert "pivot_mode" not in manifest["request"]
    assert "atlas_hint" not in manifest["request"]


def test_sprite_profile_incompatible_without_background_removal() -> None:
    catalog = load_builtin_catalog(BUILTIN)
    profile = catalog.generation_profiles["ps1_character_sprite"]
    result = evaluate_profile_compatibility(
        profile,
        supported_asset_types=["sprite", "icon", "texture"],
        negative_prompt_supported=True,
        import_profile_ids=set(catalog.import_profiles),
        template_ids=set(catalog.prompt_templates),
        negative_ids=set(catalog.negative_prompt_profiles),
        supported_transparency_strategies=["none", "background_removal"],
        background_removal_available=False,
    )
    assert result.compatible is False
    assert any(issue.code == "BACKGROUND_REMOVAL_UNAVAILABLE" for issue in result.issues)


def test_builtin_sprite_profiles_load() -> None:
    catalog = load_builtin_catalog(BUILTIN)
    assert "ps1_character_sprite" in catalog.generation_profiles
    assert "ps1_item_icon" in catalog.generation_profiles
    assert "ps1_weapon_icon" in catalog.generation_profiles
    sprite = catalog.generation_profiles["ps1_character_sprite"]
    assert sprite.generation_defaults.transparency_strategy == "background_removal"
    assert sprite.unity.pivot_mode == "bottom_center"
    assert sprite.unity.atlas_hint == "characters"
    icon = catalog.generation_profiles["ps1_item_icon"]
    assert icon.unity.pivot_mode == "center"
    assert icon.unity.atlas_hint == "items"
