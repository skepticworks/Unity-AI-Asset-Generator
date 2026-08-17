"""Domain models for managed local model installs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from unity_ai_assets.core.version import (
    MODEL_METADATA_SCHEMA_NAME,
    MODEL_METADATA_SCHEMA_VERSION,
)
from unity_ai_assets.domain.enums import (
    ModelCompatibilitySchemaStatus,
    ModelInstallStatus,
    ModelSourceType,
    ModelValidationState,
)
from unity_ai_assets.domain.model_compatibility import ModelCompatibilityManifest

HASH_ALGORITHM_SHA256 = "sha256"
METADATA_FILENAME = ".metadata.json"
COMPATIBILITY_FILENAME = ".compatibility.json"
REGISTRY_FILENAME = ".registry.json"
STAGING_DIRNAME = ".staging"


@dataclass(frozen=True, slots=True)
class ModelFileHash:
    """SHA-256 digest and size for one file relative to the model root."""

    path: str
    sha256: str
    byte_size: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "byte_size": self.byte_size}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelFileHash:
        return cls(
            path=str(payload.get("path") or ""),
            sha256=str(payload.get("sha256") or ""),
            byte_size=int(payload.get("byte_size") or 0),
        )


@dataclass(frozen=True, slots=True)
class ModelLicenseInfo:
    """License provenance. Unknown values stay explicit; never invented."""

    known: bool = False
    name: str | None = None
    url: str | None = None
    file: str | None = None
    identifier: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "known": self.known,
            "name": self.name,
            "url": self.url,
            "file": self.file,
            "identifier": self.identifier,
        }

    @classmethod
    def unknown(cls) -> ModelLicenseInfo:
        return cls(known=False)

    @classmethod
    def from_dict(cls, payload: object) -> ModelLicenseInfo:
        if not isinstance(payload, dict):
            return cls.unknown()
        name = _optional_str(payload.get("name"))
        identifier = _optional_str(payload.get("identifier"))
        url = _optional_str(payload.get("url"))
        file_name = _optional_str(payload.get("file"))
        known = bool(payload.get("known"))
        if not known and (name or identifier):
            known = True
        return cls(
            known=known,
            name=name,
            url=url,
            file=file_name,
            identifier=identifier,
        )


@dataclass(frozen=True, slots=True)
class ModelValidationIssue:
    """A single validation finding (missing file, hash mismatch, etc.)."""

    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.path:
            payload["path"] = self.path
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelValidationIssue:
        return cls(
            code=str(payload.get("code") or "VALIDATION_ISSUE"),
            message=str(payload.get("message") or ""),
            path=_optional_str(payload.get("path")),
        )


@dataclass(frozen=True, slots=True)
class ModelValidationReport:
    """Latest validation outcome for an installed model."""

    state: ModelValidationState
    checked_at: str | None
    issues: tuple[ModelValidationIssue, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return self.state is ModelValidationState.VALID and not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "checked_at": self.checked_at,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, payload: object) -> ModelValidationReport:
        if not isinstance(payload, dict):
            return cls(state=ModelValidationState.UNKNOWN, checked_at=None)
        raw_state = str(payload.get("state") or ModelValidationState.UNKNOWN.value)
        try:
            state = ModelValidationState(raw_state)
        except ValueError:
            state = ModelValidationState.UNKNOWN
        issues_raw = payload.get("issues")
        issues: list[ModelValidationIssue] = []
        if isinstance(issues_raw, list):
            for item in issues_raw:
                if isinstance(item, dict):
                    issues.append(ModelValidationIssue.from_dict(item))
        return cls(
            state=state,
            checked_at=_optional_str(payload.get("checked_at")),
            issues=tuple(issues),
        )


@dataclass(frozen=True, slots=True)
class InstalledModel:
    """A managed model after a successful install (or a failed leftover)."""

    id: str
    name: str
    source: ModelSourceType
    source_identifier: str
    install_path: str
    status: ModelInstallStatus
    usable: bool
    model_type: str
    family: str
    validation: ModelValidationReport
    license: ModelLicenseInfo
    files: tuple[ModelFileHash, ...]
    hash_algorithm: str = HASH_ALGORITHM_SHA256
    version: str | None = None
    revision: str | None = None
    source_url: str | None = None
    pipeline_class: str | None = None
    installed_at: str | None = None
    size_bytes: int | None = None
    compatibility: ModelCompatibilityManifest | None = None
    compatibility_schema_status: ModelCompatibilitySchemaStatus = (
        ModelCompatibilitySchemaStatus.MISSING
    )

    @property
    def is_usable(self) -> bool:
        return (
            self.usable
            and self.status is ModelInstallStatus.INSTALLED
            and self.validation.state is ModelValidationState.VALID
        )

    def to_metadata_dict(self) -> dict[str, Any]:
        return {
            "schema_name": MODEL_METADATA_SCHEMA_NAME,
            "schema_version": MODEL_METADATA_SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "revision": self.revision,
            "source": self.source.value,
            "source_identifier": self.source_identifier,
            "source_url": self.source_url,
            "license": self.license.to_dict(),
            "model_type": self.model_type,
            "pipeline_class": self.pipeline_class,
            "family": self.family,
            "installed_at": self.installed_at,
            "status": self.status.value,
            "usable": self.usable,
            "size_bytes": self.size_bytes,
            "validation": self.validation.to_dict(),
            "files": [item.to_dict() for item in self.files],
            "hash_algorithm": self.hash_algorithm,
        }

    @classmethod
    def from_metadata_dict(
        cls,
        payload: dict[str, Any],
        *,
        install_path: str,
        compatibility: ModelCompatibilityManifest | None = None,
    ) -> InstalledModel:
        source_raw = str(payload.get("source") or ModelSourceType.LOCAL_DIRECTORY.value)
        try:
            source = ModelSourceType(source_raw)
        except ValueError:
            source = ModelSourceType.LOCAL_DIRECTORY
        status_raw = str(payload.get("status") or ModelInstallStatus.INVALID.value)
        try:
            status = ModelInstallStatus(status_raw)
        except ValueError:
            status = ModelInstallStatus.INVALID
        files_raw = payload.get("files")
        files: list[ModelFileHash] = []
        if isinstance(files_raw, list):
            for item in files_raw:
                if isinstance(item, dict):
                    files.append(ModelFileHash.from_dict(item))
        compat_status = (
            compatibility.schema_status
            if compatibility is not None
            else ModelCompatibilitySchemaStatus.MISSING
        )
        size_raw = payload.get("size_bytes")
        size_bytes = int(size_raw) if isinstance(size_raw, int) else None
        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("id") or "Unknown model"),
            source=source,
            source_identifier=str(payload.get("source_identifier") or payload.get("id") or ""),
            install_path=install_path,
            status=status,
            usable=bool(payload.get("usable")),
            model_type=str(payload.get("model_type") or "unknown"),
            family=str(payload.get("family") or "unknown"),
            validation=ModelValidationReport.from_dict(payload.get("validation")),
            license=ModelLicenseInfo.from_dict(payload.get("license")),
            files=tuple(files),
            hash_algorithm=str(payload.get("hash_algorithm") or HASH_ALGORITHM_SHA256),
            version=_optional_str(payload.get("version")),
            revision=_optional_str(payload.get("revision")),
            source_url=_optional_str(payload.get("source_url")),
            pipeline_class=_optional_str(payload.get("pipeline_class")),
            installed_at=_optional_str(payload.get("installed_at")),
            size_bytes=size_bytes,
            compatibility=compatibility,
            compatibility_schema_status=compat_status,
        )


@dataclass(frozen=True, slots=True)
class ModelStorageStatus:
    """Configured storage directory health without walking model files."""

    directory: str
    exists: bool
    accessible: bool
    writable: bool
    created: bool = False
    issue: str | None = None
    search_paths: tuple[str, ...] = field(default_factory=tuple)
    free_bytes: int | None = None
    total_volume_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ModelDiskUsage:
    """Cached disk usage for managed models."""

    total_bytes: int
    models: tuple[tuple[str, int], ...]
    free_bytes: int | None
    volume_total_bytes: int | None
    calculated_at: str
    stale: bool = False


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
