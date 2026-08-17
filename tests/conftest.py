"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from unity_ai_assets.core.config import Settings, clear_settings_cache
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    path = tmp_path / "generated"
    path.mkdir()
    return path


@pytest.fixture
def settings(output_dir: Path, tmp_path: Path) -> Settings:
    clear_settings_cache()
    return Settings(
        model_id="fake/test-model",
        model_family="sd15",
        model_display_name="Fake Test Model",
        device="cpu",
        torch_dtype="float32",
        output_directory=output_dir,
        model_storage_directory=tmp_path / "models",
        max_width=1024,
        max_height=1024,
        enable_cpu_offload=False,
        local_files_only=True,
        log_level="WARNING",
        app_version="0.3.0-test",
    )


@pytest.fixture
def fake_backend() -> FakeImageGenerationBackend:
    return FakeImageGenerationBackend(device_name="cpu", model_loaded=False)


@pytest.fixture
def client(settings: Settings, fake_backend: FakeImageGenerationBackend) -> TestClient:
    app = create_app(settings=settings, backend=fake_backend)
    with TestClient(app) as test_client:
        yield test_client
