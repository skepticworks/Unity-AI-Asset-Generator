"""Tests for managed model storage, install, validation, hashes, offline, and delete."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from tests.helpers.fake_diffusers import write_fake_diffusers_model
from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import (
    ModelDeleteError,
    ModelNotFoundError,
    ModelOutsideStorageBoundaryError,
    ModelValidationError,
    OfflineOperationUnavailableError,
)
from unity_ai_assets.domain.enums import ModelSourceType, ModelValidationState
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.domain.model_compatibility import (
    build_manifest_from_pipeline,
    parse_compatibility_manifest,
)
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.main import create_app
from unity_ai_assets.services.capability_service import CapabilityService
from unity_ai_assets.services.model_installer import CopyTreeFetcher
from unity_ai_assets.services.model_paths import assert_within_storage, slugify_model_id
from unity_ai_assets.services.model_service import ModelService
from unity_ai_assets.services.model_validator import compute_file_hashes, validate_model_directory


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "model_id": "fake/test-model",
        "model_family": "sd15",
        "device": "cpu",
        "output_directory": tmp_path / "generated",
        "model_storage_directory": tmp_path / "models",
        "offline_mode": False,
        "log_level": "WARNING",
        "app_version": "0.10.0-test",
    }
    values.update(overrides)
    (tmp_path / "generated").mkdir(exist_ok=True)
    return Settings(**values)  # type: ignore[arg-type]


def _service(tmp_path: Path, **overrides: object) -> ModelService:
    settings = _settings(tmp_path, **overrides)
    fetcher = CopyTreeFetcher(tmp_path / "hf-source")
    return ModelService(settings, huggingface_fetcher=fetcher)


def test_slugify_rejects_parent_segments() -> None:
    with pytest.raises(ModelOutsideStorageBoundaryError):
        slugify_model_id("../escape")


def test_storage_boundary_rejects_paths_outside_root(tmp_path: Path) -> None:
    storage = tmp_path / "models"
    storage.mkdir()
    outsider = tmp_path / "other" / "weights.safetensors"
    outsider.parent.mkdir()
    outsider.write_bytes(b"nope")
    with pytest.raises(ModelOutsideStorageBoundaryError):
        assert_within_storage(outsider, [storage])


def test_storage_missing_directory_is_created(tmp_path: Path) -> None:
    settings = _settings(tmp_path, model_storage_directory=tmp_path / "missing-models")
    service = ModelService(settings)
    status = service.storage_status()
    assert status.exists is True
    assert status.accessible is True
    assert (tmp_path / "missing-models").is_dir()


def test_storage_change_retains_previous_search_path(tmp_path: Path) -> None:
    first = tmp_path / "models-a"
    second = tmp_path / "models-b"
    service = _service(tmp_path, model_storage_directory=first)
    source = write_fake_diffusers_model(tmp_path / "src-a")
    installed = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/a",
        path=str(source),
        display_name="Model A",
    )
    service.set_storage_directory(second)
    discovered = service.list_models()
    ids = {item.id for item in discovered}
    assert installed.id in ids
    assert any(str(first.resolve()) in path for path in service.storage_status().search_paths)


def test_incomplete_install_is_not_registered(tmp_path: Path) -> None:
    service = _service(tmp_path)
    empty = tmp_path / "empty-model"
    empty.mkdir()
    (empty / "readme.txt").write_text("not a model", encoding="utf-8")
    with pytest.raises(ModelValidationError):
        service.install(
            source=ModelSourceType.LOCAL_DIRECTORY.value,
            identifier="local/empty",
            path=str(empty),
        )
    assert service.list_models() == []
    assert not (service.storage_directory / "local__empty").exists()


def test_local_install_persists_metadata_and_hashes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="acme/sd15",
        path=str(source),
        display_name="Acme SD 1.5",
        revision="abc123",
    )
    assert model.is_usable
    assert model.name == "Acme SD 1.5"
    assert model.revision == "abc123"
    assert model.family == "sd15"
    assert model.license.known is False
    assert model.license.name is None
    assert model.files
    assert all(len(item.sha256) == 64 for item in model.files)
    metadata_path = Path(model.install_path) / ".metadata.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["usable"] is True
    assert payload["license"]["known"] is False


def test_hash_revalidation_detects_modified_and_missing_files(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="hash/model",
        path=str(source),
    )
    target = Path(model.install_path) / "unet" / "diffusion_pytorch_model.safetensors"
    target.write_bytes(b"tampered")
    updated = service.revalidate(model.id)
    assert updated.usable is False
    assert updated.validation.state is ModelValidationState.INVALID
    assert any(issue.code == "HASH_MISMATCH" for issue in updated.validation.issues)

    target.unlink()
    missing = service.revalidate(model.id)
    assert any(issue.code == "FILE_MISSING" for issue in missing.validation.issues)


def test_huggingface_install_uses_fetcher_and_records_license(tmp_path: Path) -> None:
    source = write_fake_diffusers_model(tmp_path / "hf-source")
    (source / "LICENSE").write_text("Apache-2.0 text", encoding="utf-8")
    settings = _settings(tmp_path)
    service = ModelService(
        settings,
        huggingface_fetcher=CopyTreeFetcher(
            source, metadata={"license_identifier": "apache-2.0", "revision": "deadbeef"}
        ),
    )
    model = service.install(
        source=ModelSourceType.HUGGINGFACE.value,
        identifier="runwayml/stable-diffusion-v1-5",
    )
    assert model.source is ModelSourceType.HUGGINGFACE
    assert model.source_url == "https://huggingface.co/runwayml/stable-diffusion-v1-5"
    assert model.license.known is True
    assert model.license.identifier == "apache-2.0"
    assert model.revision == "deadbeef"


def test_offline_blocks_remote_install_but_lists_local_models(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    installed = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/offline",
        path=str(source),
    )
    service.set_offline_mode(True)
    with pytest.raises(OfflineOperationUnavailableError) as exc:
        service.install(
            source=ModelSourceType.HUGGINGFACE.value,
            identifier="runwayml/stable-diffusion-v1-5",
        )
    assert exc.value.code.value == "OFFLINE_OPERATION_UNAVAILABLE"
    listed = service.list_models(usable_only=True)
    assert listed[0].id == installed.id
    assert listed[0].is_usable


def test_compatibility_manifest_unknown_major_is_safe(tmp_path: Path) -> None:
    parsed = parse_compatibility_manifest(
        {
            "schema_name": "model-compatibility",
            "schema_version": "2.0",
            "model_family": "sdxl",
            "supported_operations": ["text_to_image"],
            "future_field": True,
        }
    )
    assert parsed.schema_status.value == "unsupported_major"
    assert parsed.is_supported_schema is False
    assert "future_field" in parsed.unknown_fields


def test_compatibility_manifest_restricts_capabilities(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    manifest = build_manifest_from_pipeline(pipeline_class="StableDiffusionPipeline")
    payload = manifest.to_dict()
    payload["supported_operations"] = ["text_to_image"]
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/txt2img-only",
        path=str(source),
        compatibility_manifest=payload,
    )
    service.activate(model.id)
    settings = _settings(tmp_path)
    backend = FakeImageGenerationBackend()
    caps = CapabilityService(
        settings,
        GenerationPolicy.from_settings(settings),
        backend,
        model_service=service,
    ).get_capabilities()
    assert caps.operations.text_to_image.supported is True
    assert caps.operations.image_to_image.supported is False
    assert caps.operations.inpainting.supported is False
    assert caps.model_management.installed_count == 1
    assert caps.model_management.active_model_id == model.id


def test_delete_requires_confirm_and_updates_registry(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/delete-me",
        path=str(source),
    )
    with pytest.raises(ModelValidationError):
        service.delete(model.id, confirm=False)
    service.delete(model.id, confirm=True)
    with pytest.raises(ModelNotFoundError):
        service.get_model(model.id)
    assert not Path(model.install_path).exists()


def test_delete_refuses_path_outside_storage(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/inside",
        path=str(source),
    )
    with pytest.raises(ModelOutsideStorageBoundaryError):
        assert_within_storage(tmp_path / "not-storage", service._registry.scan_roots())
    # Deleting the installed model still works because it is inside storage.
    service.delete(model.id, confirm=True)


def test_delete_readonly_files(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/readonly",
        path=str(source),
    )
    weight = Path(model.install_path) / "unet" / "diffusion_pytorch_model.safetensors"
    os.chmod(weight, stat.S_IREAD)
    service.delete(model.id, confirm=True)
    assert not Path(model.install_path).exists()


def test_delete_partial_failure_marks_unusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/partial",
        path=str(source),
    )
    original_unlink = Path.unlink

    def flaky_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.suffix == ".safetensors":
            raise PermissionError("in use")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    with pytest.raises(ModelDeleteError):
        service.delete(model.id, confirm=True)
    leftover = service.get_model(model.id)
    assert leftover.usable is False
    assert leftover.status.value == "deletion_failed"


def test_disk_usage_is_cached_until_refresh(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = write_fake_diffusers_model(tmp_path / "sd15")
    model = service.install(
        source=ModelSourceType.LOCAL_DIRECTORY.value,
        identifier="local/size",
        path=str(source),
    )
    first = service.disk_usage(refresh=True)
    assert first.total_bytes > 0
    assert dict(first.models)[model.id] > 0
    cached = service.cached_disk_usage()
    assert cached is not None
    assert cached.calculated_at == first.calculated_at


def test_validate_directory_without_index(tmp_path: Path) -> None:
    folder = tmp_path / "not-a-model"
    folder.mkdir()
    report = validate_model_directory(folder)
    assert report.state is ModelValidationState.INVALID
    assert any(issue.code == "MODEL_INDEX_MISSING" for issue in report.issues)


def test_compute_hashes_stable(tmp_path: Path) -> None:
    root = write_fake_diffusers_model(tmp_path / "hash")
    first = compute_file_hashes(root)
    second = compute_file_hashes(root)
    assert {item.path: item.sha256 for item in first} == {
        item.path: item.sha256 for item in second
    }


def test_models_api_install_list_validate_delete(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings=settings, backend=FakeImageGenerationBackend())
    source = write_fake_diffusers_model(tmp_path / "api-src")
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        listed = client.get("/api/v1/models")
        assert listed.status_code == 200
        body = listed.json()
        assert body["models"] == []
        assert body["offline_mode"] is False
        assert "directory" in body["storage"]

        installed = client.post(
            "/api/v1/models/install",
            json={
                "source": "local_directory",
                "identifier": "api/local",
                "path": str(source),
                "display_name": "API Local",
            },
        )
        assert installed.status_code == 200
        model_id = installed.json()["id"]
        assert installed.json()["usable"] is True
        assert installed.json()["license"]["known"] is False

        caps = client.get("/api/v1/capabilities")
        assert caps.status_code == 200
        assert caps.json()["model_management"]["installed_count"] == 1
        assert caps.json()["schemas"]["capabilities"] == "1.7"

        validated = client.post(f"/api/v1/models/{model_id}/validate")
        assert validated.status_code == 200
        assert validated.json()["validation"]["state"] == "valid"

        usage = client.post("/api/v1/models/disk-usage/refresh")
        assert usage.status_code == 200
        assert usage.json()["total_bytes"] > 0

        denied = client.delete(f"/api/v1/models/{model_id}")
        assert denied.status_code == 422

        deleted = client.delete(f"/api/v1/models/{model_id}?confirm=true")
        assert deleted.status_code == 204
        missing = client.get(f"/api/v1/models/{model_id}")
        assert missing.status_code == 404


def test_models_api_offline_remote_install(tmp_path: Path) -> None:
    settings = _settings(tmp_path, offline_mode=True)
    app = create_app(settings=settings, backend=FakeImageGenerationBackend())
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/models/install",
            json={"source": "huggingface", "identifier": "runwayml/stable-diffusion-v1-5"},
        )
        assert response.status_code == 503
        error = response.json()["error"]
        assert error["code"] == "OFFLINE_OPERATION_UNAVAILABLE"
        assert error["details"]["operation"] == "install"
