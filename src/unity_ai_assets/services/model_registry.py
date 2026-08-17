"""Atomic registry and on-disk discovery for managed models."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.core.version import MODEL_REGISTRY_SCHEMA_NAME, MODEL_REGISTRY_SCHEMA_VERSION
from unity_ai_assets.domain.installed_models import (
    COMPATIBILITY_FILENAME,
    METADATA_FILENAME,
    REGISTRY_FILENAME,
    InstalledModel,
)
from unity_ai_assets.domain.model_compatibility import parse_compatibility_manifest
from unity_ai_assets.services.model_paths import is_within_directory, resolve_existing_path

logger = get_logger(__name__)


class ModelRegistry:
    """Index of installed models plus extra search paths.

    The registry file is a convenience index. Discovery also scans storage
    directories for ``.metadata.json`` so models remain visible after the
    configured storage path changes, as long as the old location is still
    listed as a search path or still contains valid metadata.
    """

    def __init__(self, storage_directory: Path, search_paths: tuple[Path, ...] = ()) -> None:
        self._storage_directory = storage_directory
        self._search_paths = list(search_paths)
        self._active_model_id: str | None = None

    @property
    def storage_directory(self) -> Path:
        return self._storage_directory

    @property
    def search_paths(self) -> tuple[Path, ...]:
        return tuple(self._search_paths)

    @property
    def active_model_id(self) -> str | None:
        return self._active_model_id

    @property
    def registry_path(self) -> Path:
        return self._storage_directory / REGISTRY_FILENAME

    def set_storage_directory(self, directory: Path, *, retain_previous: bool = True) -> None:
        previous = self._storage_directory
        self._storage_directory = directory
        self._load_registry_file()
        if retain_previous and previous != directory and previous.exists():
            self.add_search_path(previous)

    def add_search_path(self, path: Path) -> None:
        resolved = resolve_existing_path(path)
        existing = {resolve_existing_path(item) for item in self._search_paths}
        if resolved in existing or resolved == resolve_existing_path(self._storage_directory):
            return
        self._search_paths.append(resolved)

    def scan_roots(self) -> list[Path]:
        roots = [resolve_existing_path(self._storage_directory)]
        seen = {roots[0]}
        for path in self._search_paths:
            resolved = resolve_existing_path(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            roots.append(resolved)
        return roots

    def load(self) -> None:
        self._load_registry_file()

    def discover(self) -> list[InstalledModel]:
        """Return models with readable metadata. Incomplete installs are omitted."""
        found: dict[str, InstalledModel] = {}
        for root in self.scan_roots():
            if not root.exists() or not root.is_dir():
                continue
            for metadata_path in root.glob(f"*/{METADATA_FILENAME}"):
                model = self._read_model(metadata_path)
                if model is None:
                    continue
                if model.id in found:
                    continue
                found[model.id] = model
        return sorted(found.values(), key=lambda item: item.name.lower())

    def get(self, model_id: str) -> InstalledModel | None:
        for model in self.discover():
            if model.id == model_id or model.source_identifier == model_id:
                return model
        return None

    def save_model_metadata(self, model: InstalledModel, directory: Path) -> None:
        payload = model.to_metadata_dict()
        self._atomic_write_json(directory / METADATA_FILENAME, payload)
        if model.compatibility is not None and model.compatibility.is_supported_schema:
            self._atomic_write_json(
                directory / COMPATIBILITY_FILENAME,
                model.compatibility.to_dict(),
            )
        self.persist_index()

    def persist_index(self) -> None:
        models = []
        for model in self.discover():
            models.append(
                {
                    "id": model.id,
                    "relative_path": Path(model.install_path).name,
                    "usable": model.is_usable,
                }
            )
        payload: dict[str, Any] = {
            "schema_name": MODEL_REGISTRY_SCHEMA_NAME,
            "schema_version": MODEL_REGISTRY_SCHEMA_VERSION,
            "active_model_id": self._active_model_id,
            "search_paths": [str(path) for path in self._search_paths],
            "models": models,
        }
        try:
            self._storage_directory.mkdir(parents=True, exist_ok=True)
            self._atomic_write_json(self.registry_path, payload)
        except OSError:
            logger.warning("Could not persist model registry at %s", self.registry_path)

    def set_active_model_id(self, model_id: str | None) -> None:
        self._active_model_id = model_id
        self.persist_index()

    def remove_from_index(self, model_id: str) -> None:
        if self._active_model_id == model_id:
            self._active_model_id = None
        self.persist_index()

    def _load_registry_file(self) -> None:
        path = self.registry_path
        if not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Skipping unreadable model registry %s", path)
            return
        if not isinstance(payload, dict):
            return
        active = payload.get("active_model_id")
        self._active_model_id = str(active) if active else None
        extra = payload.get("search_paths")
        if isinstance(extra, list):
            for item in extra:
                if item:
                    self.add_search_path(Path(str(item)))

    def _read_model(self, metadata_path: Path) -> InstalledModel | None:
        directory = metadata_path.parent
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Skipping unreadable model metadata %s", metadata_path)
            return None
        if not isinstance(payload, dict):
            return None
        status = str(payload.get("status") or "")
        if status in {"installing", ""}:
            return None
        compatibility = None
        compat_path = directory / COMPATIBILITY_FILENAME
        if compat_path.is_file():
            try:
                compat_payload = json.loads(compat_path.read_text(encoding="utf-8"))
                compatibility = parse_compatibility_manifest(compat_payload)
            except (OSError, json.JSONDecodeError):
                logger.warning("Skipping unreadable compatibility manifest %s", compat_path)
        try:
            return InstalledModel.from_metadata_dict(
                payload,
                install_path=str(resolve_existing_path(directory)),
                compatibility=compatibility,
            )
        except (TypeError, ValueError):
            logger.warning("Skipping invalid model metadata %s", metadata_path)
            return None

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise


def model_directory_is_managed(directory: Path, roots: list[Path]) -> bool:
    """True when a directory sits inside a scanned storage root."""
    resolved = resolve_existing_path(directory)
    return any(is_within_directory(resolved, root) for root in roots)
