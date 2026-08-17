"""Staged installation of Diffusers models from local directories or Hugging Face."""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from unity_ai_assets.core.errors import (
    ModelInstallError,
    ModelValidationError,
    OfflineOperationUnavailableError,
)
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.enums import ModelSourceType
from unity_ai_assets.domain.installed_models import (
    STAGING_DIRNAME,
    ModelLicenseInfo,
)
from unity_ai_assets.domain.model_compatibility import (
    build_manifest_from_pipeline,
    parse_compatibility_manifest,
)
from unity_ai_assets.services.model_paths import slugify_model_id
from unity_ai_assets.services.model_validator import (
    infer_family,
    pipeline_class_from_index,
    read_model_index,
    required_components_from_index,
    utc_now_iso,
    validate_model_directory,
)

logger = get_logger(__name__)


class HuggingFaceFetcher(Protocol):
    """Downloads a snapshot into ``destination`` and optionally returns card metadata."""

    def download(
        self,
        repo_id: str,
        revision: str | None,
        destination: Path,
    ) -> dict[str, Any]:
        """Populate ``destination`` with model files. May raise ModelInstallError."""
        ...


class HuggingFaceHubFetcher:
    """Production fetcher using huggingface_hub.snapshot_download."""

    def download(
        self,
        repo_id: str,
        revision: str | None,
        destination: Path,
    ) -> dict[str, Any]:
        try:
            from huggingface_hub import HfApi, snapshot_download
        except ImportError as exc:
            raise ModelInstallError(
                "huggingface_hub is not installed; cannot download remote models."
            ) from exc
        try:
            snapshot_download(
                repo_id=repo_id,
                revision=revision,
                local_dir=str(destination),
            )
        except Exception as exc:  # noqa: BLE001
            raise ModelInstallError(
                "Failed to download the Hugging Face model snapshot.",
                details={"source": repo_id, "reason": type(exc).__name__},
            ) from exc
        metadata: dict[str, Any] = {}
        try:
            info = HfApi().model_info(repo_id, revision=revision)
        except Exception:  # noqa: BLE001
            return metadata
        license_id = getattr(info, "license", None)
        card = getattr(info, "card_data", None) or getattr(info, "cardData", None)
        if not license_id and isinstance(card, dict):
            license_id = card.get("license")
        if hasattr(card, "license") and not license_id:
            license_id = getattr(card, "license", None)
        if license_id:
            metadata["license_identifier"] = str(license_id)
        sha = getattr(info, "sha", None)
        if sha:
            metadata["revision"] = str(sha)
        return metadata


class CopyTreeFetcher:
    """Test double that copies a prepared directory instead of using the network."""

    def __init__(self, source_tree: Path, metadata: dict[str, Any] | None = None) -> None:
        self._source_tree = source_tree
        self._metadata = metadata or {}

    def download(
        self,
        repo_id: str,
        revision: str | None,
        destination: Path,
    ) -> dict[str, Any]:
        if not self._source_tree.is_dir():
            raise ModelInstallError(
                "Fake Hugging Face source tree is missing.",
                details={"repo_id": repo_id, "revision": revision},
            )
        shutil.copytree(self._source_tree, destination, dirs_exist_ok=True)
        return dict(self._metadata)


class ModelInstaller:
    """Copy or download into a staging directory, validate, then promote."""

    def __init__(
        self,
        storage_directory: Path,
        *,
        huggingface_fetcher: HuggingFaceFetcher | None = None,
        offline: bool = False,
        clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._storage_directory = storage_directory
        self._fetcher = huggingface_fetcher or HuggingFaceHubFetcher()
        self._offline = offline
        self._clock = clock

    @property
    def staging_root(self) -> Path:
        return self._storage_directory / STAGING_DIRNAME

    def set_offline(self, offline: bool) -> None:
        self._offline = offline

    def set_storage_directory(self, directory: Path) -> None:
        self._storage_directory = directory

    def cleanup_staging(self) -> None:
        root = self.staging_root
        if not root.exists():
            return
        shutil.rmtree(root, ignore_errors=True)

    def install(
        self,
        *,
        source: ModelSourceType,
        identifier: str,
        local_path: Path | None = None,
        revision: str | None = None,
        display_name: str | None = None,
        compatibility_payload: dict[str, Any] | None = None,
    ) -> Path:
        """Stage, validate, and move a model into managed storage.

        Returns the final model directory. Does not write registry metadata;
        the caller persists ``InstalledModel`` after hashing.
        """
        slug = slugify_model_id(identifier)
        destination = self._storage_directory / slug
        if destination.exists():
            raise ModelInstallError(
                f"A model is already installed at '{slug}'.",
                details={"id": slug},
            )

        install_id = uuid.uuid4().hex
        staging = self.staging_root / install_id
        try:
            staging.mkdir(parents=True, exist_ok=True)
            if source is ModelSourceType.HUGGINGFACE:
                if self._offline:
                    raise OfflineOperationUnavailableError(
                        "Installing from Hugging Face requires network access.",
                        details={"operation": "install", "source": "huggingface"},
                    )
                remote_meta = self._fetcher.download(identifier, revision, staging)
            elif source is ModelSourceType.LOCAL_DIRECTORY:
                if local_path is None:
                    raise ModelInstallError("A local directory path is required.")
                self._copy_local(local_path, staging)
                remote_meta = {}
            else:
                raise ModelInstallError(f"Unsupported model source '{source}'.")

            report = validate_model_directory(staging)
            if report.state.value != "valid":
                raise ModelValidationError(
                    "The staged model failed validation and was not registered.",
                    details={
                        "issues": [issue.to_dict() for issue in report.issues],
                    },
                )

            index = read_model_index(staging)
            pipeline_class = pipeline_class_from_index(index)
            family = infer_family(staging)
            if compatibility_payload is not None:
                manifest = parse_compatibility_manifest(compatibility_payload)
            else:
                manifest = build_manifest_from_pipeline(
                    pipeline_class=pipeline_class,
                    required_components=required_components_from_index(index),
                    family=family,
                )
            (staging / ".compatibility.json").write_text(
                json.dumps(manifest.to_dict(), indent=2),
                encoding="utf-8",
            )

            destination.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(destination)
            # Stash remote metadata beside the tree via a sidecar the service reads.
            sidecar = destination / ".install-source.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "id": slug,
                        "name": display_name or identifier,
                        "source": source.value,
                        "source_identifier": identifier,
                        "revision": revision or remote_meta.get("revision"),
                        "source_url": _source_url(source, identifier),
                        "license_identifier": remote_meta.get("license_identifier"),
                        "pipeline_class": pipeline_class,
                        "family": family,
                        "installed_at": self._clock(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return destination
        except (ModelValidationError, OfflineOperationUnavailableError, ModelInstallError):
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(staging, ignore_errors=True)
            raise ModelInstallError(
                "Model installation failed before the model could be registered.",
                details={"reason": type(exc).__name__},
            ) from exc

    def _copy_local(self, source: Path, destination: Path) -> None:
        if not source.exists() or not source.is_dir():
            raise ModelInstallError(
                "Local model directory does not exist.",
                details={"path": str(source)},
            )
        try:
            shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False)
        except OSError as exc:
            raise ModelInstallError(
                "Failed to copy the local model directory into staging.",
                details={"reason": type(exc).__name__},
            ) from exc


def license_from_install_sidecar(directory: Path) -> ModelLicenseInfo:
    sidecar = directory / ".install-source.json"
    if not sidecar.is_file():
        license_file = _find_license_file(directory)
        return ModelLicenseInfo(known=False, file=license_file)
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ModelLicenseInfo.unknown()
    identifier = payload.get("license_identifier")
    if identifier:
        return ModelLicenseInfo(
            known=True,
            identifier=str(identifier),
            name=str(identifier),
            file=_find_license_file(directory),
        )
    return ModelLicenseInfo(known=False, file=_find_license_file(directory))


def read_install_sidecar(directory: Path) -> dict[str, Any]:
    sidecar = directory / ".install-source.json"
    if not sidecar.is_file():
        return {}
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _find_license_file(directory: Path) -> str | None:
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
        if (directory / name).is_file():
            return name
    return None


def _source_url(source: ModelSourceType, identifier: str) -> str | None:
    if source is ModelSourceType.HUGGINGFACE:
        return f"https://huggingface.co/{identifier}"
    return None
