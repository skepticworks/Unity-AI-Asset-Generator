"""Pydantic schemas for managed model APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from unity_ai_assets.domain.installed_models import (
    InstalledModel,
    ModelDiskUsage,
    ModelStorageStatus,
)


class ModelLicenseSchema(BaseModel):
    """License provenance. ``known`` is false when the license was not provided."""

    known: bool = False
    name: str | None = None
    url: str | None = None
    file: str | None = None
    identifier: str | None = None


class ModelValidationIssueSchema(BaseModel):
    """One validation finding."""

    code: str
    message: str
    path: str | None = None


class ModelValidationSchema(BaseModel):
    """Latest validation outcome."""

    state: str
    checked_at: str | None = None
    issues: list[ModelValidationIssueSchema] = Field(default_factory=list)


class ModelCompatibilitySchema(BaseModel):
    """Public view of a versioned compatibility manifest."""

    schema_name: str | None = None
    schema_version: str | None = None
    schema_status: str
    architecture: str | None = None
    pipeline_type: str | None = None
    pipeline_class: str | None = None
    model_family: str | None = None
    supported_operations: list[str] = Field(default_factory=list)
    required_components: list[str] = Field(default_factory=list)
    backend_engine: str | None = None
    generation_modes: list[str] = Field(default_factory=list)


class ModelFileHashSchema(BaseModel):
    """Persisted SHA-256 for one model file."""

    path: str
    sha256: str
    byte_size: int


class InstalledModelSchema(BaseModel):
    """A managed model as returned to clients."""

    id: str
    name: str
    version: str | None = None
    revision: str | None = None
    source: str
    source_identifier: str
    source_url: str | None = None
    license: ModelLicenseSchema
    model_type: str
    pipeline_class: str | None = None
    family: str
    installed_at: str | None = None
    status: str
    usable: bool
    active: bool = False
    size_bytes: int | None = None
    validation: ModelValidationSchema
    compatibility: ModelCompatibilitySchema
    hash_algorithm: str = "sha256"
    files: list[ModelFileHashSchema] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, model: InstalledModel, *, active_id: str | None) -> InstalledModelSchema:
        compat = model.compatibility
        compatibility = ModelCompatibilitySchema(
            schema_name=compat.schema_name if compat else None,
            schema_version=compat.schema_version if compat else None,
            schema_status=model.compatibility_schema_status.value,
            architecture=compat.architecture if compat else None,
            pipeline_type=compat.pipeline_type if compat else None,
            pipeline_class=compat.pipeline_class if compat else model.pipeline_class,
            model_family=compat.model_family if compat else model.family,
            supported_operations=list(compat.supported_operations) if compat else [],
            required_components=list(compat.required_components) if compat else [],
            backend_engine=compat.backend_engine if compat else None,
            generation_modes=list(compat.generation_modes) if compat else [],
        )
        return cls(
            id=model.id,
            name=model.name,
            version=model.version,
            revision=model.revision,
            source=model.source.value,
            source_identifier=model.source_identifier,
            source_url=model.source_url,
            license=ModelLicenseSchema(
                known=model.license.known,
                name=model.license.name,
                url=model.license.url,
                file=model.license.file,
                identifier=model.license.identifier,
            ),
            model_type=model.model_type,
            pipeline_class=model.pipeline_class,
            family=model.family,
            installed_at=model.installed_at,
            status=model.status.value,
            usable=model.is_usable,
            active=active_id == model.id,
            size_bytes=model.size_bytes,
            validation=ModelValidationSchema(
                state=model.validation.state.value,
                checked_at=model.validation.checked_at,
                issues=[
                    ModelValidationIssueSchema(
                        code=issue.code, message=issue.message, path=issue.path
                    )
                    for issue in model.validation.issues
                ],
            ),
            compatibility=compatibility,
            hash_algorithm=model.hash_algorithm,
            files=[
                ModelFileHashSchema(path=item.path, sha256=item.sha256, byte_size=item.byte_size)
                for item in model.files
            ],
        )


class ModelListResponse(BaseModel):
    """Installed models plus storage summary."""

    models: list[InstalledModelSchema]
    storage: ModelStorageSchema
    offline_mode: bool
    active_model_id: str | None = None


class ModelStorageSchema(BaseModel):
    """Configured storage directory health."""

    directory: str
    exists: bool
    accessible: bool
    writable: bool
    created: bool = False
    issue: str | None = None
    search_paths: list[str] = Field(default_factory=list)
    free_bytes: int | None = None
    total_volume_bytes: int | None = None

    @classmethod
    def from_domain(cls, status: ModelStorageStatus) -> ModelStorageSchema:
        return cls(
            directory=status.directory,
            exists=status.exists,
            accessible=status.accessible,
            writable=status.writable,
            created=status.created,
            issue=status.issue,
            search_paths=list(status.search_paths),
            free_bytes=status.free_bytes,
            total_volume_bytes=status.total_volume_bytes,
        )


class ModelStorageUpdateRequest(BaseModel):
    """Change the primary model-storage directory."""

    directory: str = Field(min_length=1)


class ModelInstallRequest(BaseModel):
    """Install from Hugging Face or a local Diffusers directory."""

    source: str = Field(description="huggingface | local_directory")
    identifier: str | None = Field(
        default=None,
        description="Hugging Face repo id or stable identifier",
    )
    path: str | None = Field(default=None, description="Local directory to copy")
    revision: str | None = None
    display_name: str | None = None
    compatibility_manifest: dict[str, Any] | None = None


class ModelOfflineRequest(BaseModel):
    """Enable or disable offline mode at runtime."""

    enabled: bool


class ModelDiskUsageModelSchema(BaseModel):
    """Per-model size."""

    id: str
    size_bytes: int


class ModelDiskUsageResponse(BaseModel):
    """Cached or freshly calculated disk usage."""

    total_bytes: int
    models: list[ModelDiskUsageModelSchema]
    free_bytes: int | None = None
    volume_total_bytes: int | None = None
    calculated_at: str
    stale: bool = False

    @classmethod
    def from_domain(cls, usage: ModelDiskUsage) -> ModelDiskUsageResponse:
        return cls(
            total_bytes=usage.total_bytes,
            models=[
                ModelDiskUsageModelSchema(id=model_id, size_bytes=size)
                for model_id, size in usage.models
            ],
            free_bytes=usage.free_bytes,
            volume_total_bytes=usage.volume_total_bytes,
            calculated_at=usage.calculated_at,
            stale=usage.stale,
        )
