"""Public model-management facade used by the API and capability assembly."""

from __future__ import annotations

import json
import os
import shutil
import stat
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import (
    ModelDeleteError,
    ModelInUseError,
    ModelNotFoundError,
    ModelOutsideStorageBoundaryError,
    ModelStorageInvalidError,
    ModelValidationError,
    OfflineOperationUnavailableError,
)
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.enums import (
    ModelCompatibilitySchemaStatus,
    ModelInstallStatus,
    ModelSourceType,
    ModelValidationState,
)
from unity_ai_assets.domain.installed_models import (
    InstalledModel,
    ModelDiskUsage,
    ModelLicenseInfo,
    ModelStorageStatus,
    ModelValidationReport,
)
from unity_ai_assets.domain.model_compatibility import parse_compatibility_manifest
from unity_ai_assets.services.model_installer import (
    HuggingFaceFetcher,
    ModelInstaller,
    license_from_install_sidecar,
    read_install_sidecar,
)
from unity_ai_assets.services.model_paths import (
    assert_within_storage,
    directory_size_bytes,
    ensure_storage_directory,
    inspect_storage_directory,
    resolve_existing_path,
    slugify_model_id,
    volume_usage,
)
from unity_ai_assets.services.model_registry import ModelRegistry
from unity_ai_assets.services.model_validator import (
    compute_file_hashes,
    utc_now_iso,
    validate_model_directory,
)

logger = get_logger(__name__)

UnloadCallback = Callable[[], bool]
InUseCallback = Callable[[], bool]


class ModelService:
    """Install, discover, validate, measure, and delete managed models."""

    def __init__(
        self,
        settings: Settings,
        *,
        huggingface_fetcher: HuggingFaceFetcher | None = None,
        unload_callback: UnloadCallback | None = None,
        in_use_callback: InUseCallback | None = None,
    ) -> None:
        self._settings = settings
        storage, _ = _try_ensure(settings.model_storage_directory)
        self._registry = ModelRegistry(storage, settings.model_storage_search_paths)
        self._registry.load()
        self._installer = ModelInstaller(
            storage,
            huggingface_fetcher=huggingface_fetcher,
            offline=settings.offline_mode,
        )
        self._installer.cleanup_staging()
        self._unload_callback = unload_callback
        self._in_use_callback = in_use_callback
        self._disk_usage: ModelDiskUsage | None = None

    def bind_runtime(
        self,
        *,
        unload_callback: UnloadCallback | None = None,
        in_use_callback: InUseCallback | None = None,
    ) -> None:
        if unload_callback is not None:
            self._unload_callback = unload_callback
        if in_use_callback is not None:
            self._in_use_callback = in_use_callback

    @property
    def offline_mode(self) -> bool:
        return bool(self._settings.offline_mode)

    @property
    def storage_directory(self) -> Path:
        return self._registry.storage_directory

    def set_offline_mode(self, enabled: bool) -> bool:
        self._settings.offline_mode = enabled
        self._installer.set_offline(enabled)
        return enabled

    def storage_status(self) -> ModelStorageStatus:
        directory = self._registry.storage_directory
        exists, accessible, writable, issue = inspect_storage_directory(directory)
        free_bytes, total_bytes = volume_usage(directory)
        return ModelStorageStatus(
            directory=str(resolve_existing_path(directory)),
            exists=exists,
            accessible=accessible,
            writable=writable,
            issue=issue,
            search_paths=tuple(str(path) for path in self._registry.search_paths),
            free_bytes=free_bytes,
            total_volume_bytes=total_bytes,
        )

    def set_storage_directory(self, directory: Path) -> ModelStorageStatus:
        resolved, created = ensure_storage_directory(directory, create=True)
        if not _is_writable(resolved):
            raise ModelStorageInvalidError(
                "The new model storage directory is not writable.",
                details={"path": str(resolved)},
            )
        previous = self._registry.storage_directory
        self._registry.set_storage_directory(resolved, retain_previous=True)
        self._registry.persist_index()
        self._installer.set_storage_directory(resolved)
        self._installer.cleanup_staging()
        self._settings.model_storage_directory = resolved
        extra = list(self._settings.model_storage_search_paths)
        if previous != resolved and previous not in extra:
            extra.append(previous)
        self._settings.model_storage_search_paths = tuple(extra)
        self._disk_usage = None
        status = self.storage_status()
        return ModelStorageStatus(
            directory=status.directory,
            exists=status.exists,
            accessible=status.accessible,
            writable=status.writable,
            created=created,
            issue=status.issue,
            search_paths=status.search_paths,
            free_bytes=status.free_bytes,
            total_volume_bytes=status.total_volume_bytes,
        )

    def list_models(self, *, usable_only: bool = False) -> list[InstalledModel]:
        models = self._registry.discover()
        if usable_only:
            return [model for model in models if model.is_usable]
        return models

    def get_model(self, model_id: str) -> InstalledModel:
        model = self._registry.get(model_id)
        if model is None:
            raise ModelNotFoundError(f"Model '{model_id}' was not found.")
        return model

    def get_active(self) -> InstalledModel | None:
        active_id = self._registry.active_model_id
        if active_id:
            model = self._registry.get(active_id)
            if model is not None and model.is_usable:
                return model
        configured = self._settings.model_id
        if configured:
            model = self._registry.get(configured)
            if model is not None and model.is_usable:
                return model
        return None

    def resolve_local_path(self, model_id: str) -> Path | None:
        model = self._registry.get(model_id)
        if model is None or not model.is_usable:
            return None
        path = Path(model.install_path)
        if path.is_dir():
            return path
        return None

    def install(
        self,
        *,
        source: str,
        identifier: str | None = None,
        path: str | None = None,
        revision: str | None = None,
        display_name: str | None = None,
        compatibility_manifest: dict[str, Any] | None = None,
    ) -> InstalledModel:
        try:
            source_type = ModelSourceType(source)
        except ValueError as exc:
            raise ModelValidationError(
                f"Unsupported model source '{source}'.",
            ) from exc

        local_path = Path(path) if path else None
        source_identifier = identifier or (str(local_path) if local_path else "")
        if not source_identifier:
            raise ModelValidationError("A source identifier or local path is required.")

        if source_type is ModelSourceType.HUGGINGFACE and self.offline_mode:
            raise OfflineOperationUnavailableError(
                "Installing from Hugging Face is unavailable while offline mode is enabled.",
                details={"operation": "install", "source": "huggingface"},
            )

        directory = self._installer.install(
            source=source_type,
            identifier=source_identifier,
            local_path=local_path,
            revision=revision,
            display_name=display_name,
            compatibility_payload=compatibility_manifest,
        )
        try:
            model = self._finalize_install(directory)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        self._disk_usage = None
        return model

    def revalidate(self, model_id: str) -> InstalledModel:
        model = self.get_model(model_id)
        directory = Path(model.install_path)
        self._assert_managed(directory)
        report = validate_model_directory(directory, expected_hashes=model.files)
        usable = report.state is ModelValidationState.VALID
        status = ModelInstallStatus.INSTALLED if usable else ModelInstallStatus.INVALID
        size_bytes = directory_size_bytes(directory)
        updated = InstalledModel(
            id=model.id,
            name=model.name,
            source=model.source,
            source_identifier=model.source_identifier,
            install_path=model.install_path,
            status=status,
            usable=usable,
            model_type=model.model_type,
            family=model.family,
            validation=report,
            license=model.license,
            files=model.files if model.files else compute_file_hashes(directory),
            hash_algorithm=model.hash_algorithm,
            version=model.version,
            revision=model.revision,
            source_url=model.source_url,
            pipeline_class=model.pipeline_class,
            installed_at=model.installed_at,
            size_bytes=size_bytes,
            compatibility=model.compatibility,
            compatibility_schema_status=model.compatibility_schema_status,
        )
        self._registry.save_model_metadata(updated, directory)
        return updated

    def activate(self, model_id: str) -> InstalledModel:
        model = self.get_model(model_id)
        if not model.is_usable:
            raise ModelValidationError(
                "Only validated models can be activated.",
                details={"id": model.id, "status": model.status.value},
            )
        self._registry.set_active_model_id(model.id)
        self._settings.model_id = model.source_identifier or model.id
        self._settings.model_family = model.family
        self._settings.model_revision = model.revision
        self._settings.model_display_name = model.name
        if self._unload_callback is not None:
            self._unload_callback()
        return model

    def delete(self, model_id: str, *, confirm: bool) -> None:
        if not confirm:
            raise ModelValidationError(
                "Deletion requires explicit confirmation.",
                details={"confirm_required": True},
            )
        model = self.get_model(model_id)
        directory = Path(model.install_path)
        self._assert_managed(directory)
        if directory == self._registry.storage_directory:
            raise ModelOutsideStorageBoundaryError(
                "Refusing to delete the model-storage root."
            )
        active = self.get_active()
        is_active = active is not None and active.id == model.id
        if is_active and self._in_use_callback is not None and self._in_use_callback():
            raise ModelInUseError(
                "The model is in use by an active generation job and cannot be deleted."
            )
        if is_active and self._unload_callback is not None:
            self._unload_callback()

        leftover = self._remove_tree(directory)
        if leftover:
            failed = InstalledModel(
                id=model.id,
                name=model.name,
                source=model.source,
                source_identifier=model.source_identifier,
                install_path=str(directory),
                status=ModelInstallStatus.DELETION_FAILED,
                usable=False,
                model_type=model.model_type,
                family=model.family,
                validation=ModelValidationReport(
                    state=ModelValidationState.INVALID,
                    checked_at=utc_now_iso(),
                    issues=(),
                ),
                license=model.license,
                files=model.files,
                hash_algorithm=model.hash_algorithm,
                version=model.version,
                revision=model.revision,
                source_url=model.source_url,
                pipeline_class=model.pipeline_class,
                installed_at=model.installed_at,
                size_bytes=model.size_bytes,
                compatibility=model.compatibility,
                compatibility_schema_status=model.compatibility_schema_status,
            )
            try:
                if directory.exists():
                    self._registry.save_model_metadata(failed, directory)
            except OSError:
                logger.warning("Could not persist deletion-failed metadata for %s", model.id)
            raise ModelDeleteError(
                "Some model files could not be deleted.",
                details={"id": model.id, "leftover": leftover},
            )

        if is_active:
            self._registry.set_active_model_id(None)
        else:
            self._registry.remove_from_index(model.id)
        self._disk_usage = None

    def disk_usage(self, *, refresh: bool = False) -> ModelDiskUsage:
        if self._disk_usage is not None and not refresh:
            return self._disk_usage
        models = self.list_models()
        per_model: list[tuple[str, int]] = []
        total = 0
        for model in models:
            size = directory_size_bytes(Path(model.install_path))
            per_model.append((model.id, size))
            total += size
            self._persist_size(model, size)
        free_bytes, volume_total = volume_usage(self._registry.storage_directory)
        report = ModelDiskUsage(
            total_bytes=total,
            models=tuple(per_model),
            free_bytes=free_bytes,
            volume_total_bytes=volume_total,
            calculated_at=utc_now_iso(),
            stale=False,
        )
        self._disk_usage = report
        return report

    def cached_disk_usage(self) -> ModelDiskUsage | None:
        return self._disk_usage

    def model_management_summary(self) -> dict[str, Any]:
        status = self.storage_status()
        models = self.list_models(usable_only=True)
        active = self.get_active()
        return {
            "supported": True,
            "offline_mode": self.offline_mode,
            "storage_configured": True,
            "storage_accessible": status.accessible,
            "storage_writable": status.writable,
            "installed_count": len(models),
            "active_model_id": active.id if active else None,
        }

    def _finalize_install(self, directory: Path) -> InstalledModel:
        sidecar = read_install_sidecar(directory)
        license_info = license_from_install_sidecar(directory)
        sidecar_path = directory / ".install-source.json"
        if sidecar_path.exists():
            with suppress(OSError):
                sidecar_path.unlink()
        hashes = compute_file_hashes(directory)
        report = validate_model_directory(directory, expected_hashes=hashes)
        if report.state is not ModelValidationState.VALID:
            raise ModelValidationError(
                "Installed files failed hash validation.",
                details={"issues": [issue.to_dict() for issue in report.issues]},
            )
        compatibility = None
        compat_path = directory / ".compatibility.json"
        if compat_path.is_file():
            try:
                compatibility = parse_compatibility_manifest(
                    json.loads(compat_path.read_text(encoding="utf-8"))
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                compatibility = None
        if not license_info.known:
            license_info = ModelLicenseInfo(
                known=False,
                name=None,
                url=None,
                file=license_info.file,
                identifier=None,
            )
        model_id = str(sidecar.get("id") or slugify_model_id(directory.name))
        size_bytes = directory_size_bytes(directory)
        model = InstalledModel(
            id=model_id,
            name=str(sidecar.get("name") or model_id),
            source=ModelSourceType(str(sidecar.get("source") or "local_directory")),
            source_identifier=str(sidecar.get("source_identifier") or model_id),
            install_path=str(resolve_existing_path(directory)),
            status=ModelInstallStatus.INSTALLED,
            usable=True,
            model_type="diffusers_pipeline",
            family=str(sidecar.get("family") or "unknown"),
            validation=report,
            license=license_info,
            files=hashes,
            version=_optional_str(sidecar.get("version")),
            revision=_optional_str(sidecar.get("revision")),
            source_url=_optional_str(sidecar.get("source_url")),
            pipeline_class=_optional_str(sidecar.get("pipeline_class")),
            installed_at=_optional_str(sidecar.get("installed_at")) or utc_now_iso(),
            size_bytes=size_bytes,
            compatibility=compatibility,
            compatibility_schema_status=(
                compatibility.schema_status
                if compatibility is not None
                else ModelCompatibilitySchemaStatus.MISSING
            ),
        )
        self._registry.save_model_metadata(model, directory)
        return model

    def _persist_size(self, model: InstalledModel, size: int) -> None:
        if model.size_bytes == size:
            return
        updated = InstalledModel(
            id=model.id,
            name=model.name,
            source=model.source,
            source_identifier=model.source_identifier,
            install_path=model.install_path,
            status=model.status,
            usable=model.usable,
            model_type=model.model_type,
            family=model.family,
            validation=model.validation,
            license=model.license,
            files=model.files,
            hash_algorithm=model.hash_algorithm,
            version=model.version,
            revision=model.revision,
            source_url=model.source_url,
            pipeline_class=model.pipeline_class,
            installed_at=model.installed_at,
            size_bytes=size,
            compatibility=model.compatibility,
            compatibility_schema_status=model.compatibility_schema_status,
        )
        try:
            self._registry.save_model_metadata(updated, Path(model.install_path))
        except OSError:
            logger.warning("Could not persist disk-usage size for %s", model.id)

    def _assert_managed(self, directory: Path) -> None:
        assert_within_storage(directory, self._registry.scan_roots(), allow_root=False)

    def _remove_tree(self, directory: Path) -> list[str]:
        leftover: list[str] = []
        if not directory.exists():
            return leftover
        for child in sorted(directory.rglob("*"), reverse=True):
            try:
                if child.is_symlink() or child.is_file():
                    _clear_readonly(child)
                    child.unlink()
                elif child.is_dir():
                    _clear_readonly(child)
                    child.rmdir()
            except OSError:
                leftover.append(str(child))
        try:
            _clear_readonly(directory)
            directory.rmdir()
        except OSError:
            if directory.exists():
                leftover.append(str(directory))
        return leftover


def _try_ensure(path: Path) -> tuple[Path, bool]:
    try:
        return ensure_storage_directory(path, create=True)
    except ModelStorageInvalidError:
        return resolve_existing_path(path), False


def _is_writable(path: Path) -> bool:
    probe = path / ".write-test.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _clear_readonly(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        if not mode & stat.S_IWRITE:
            os.chmod(path, mode | stat.S_IWRITE)
    except OSError:
        pass


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
