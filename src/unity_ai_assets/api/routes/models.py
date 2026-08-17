"""Managed model installation, validation, storage, and deletion endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request, status

from unity_ai_assets.api.schemas.models import (
    InstalledModelSchema,
    ModelDiskUsageResponse,
    ModelInstallRequest,
    ModelListResponse,
    ModelOfflineRequest,
    ModelStorageSchema,
    ModelStorageUpdateRequest,
)
from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import FieldIssue, GenerationRequestInvalidError
from unity_ai_assets.services.model_paths import slugify_model_id
from unity_ai_assets.services.model_service import ModelService

router = APIRouter(prefix="/api/v1", tags=["models"])


def _service(request: Request) -> ModelService:
    service = request.app.state.model_service
    if not isinstance(service, ModelService):
        raise RuntimeError("Model service is not configured on the application.")
    return service


def _active_id(service: ModelService) -> str | None:
    active = service.get_active()
    return active.id if active else None


def _validate_model_id(model_id: str) -> str:
    raw = model_id.strip()
    if not raw:
        raise GenerationRequestInvalidError(
            "model_id must not be empty",
            field_issues={
                "model_id": [
                    FieldIssue(code=FieldIssueCode.FIELD_REQUIRED, message="model_id is required.")
                ]
            },
        )
    if ".." in raw or "/" in raw or "\\" in raw:
        raise GenerationRequestInvalidError(
            "model_id must not contain path segments",
            field_issues={
                "model_id": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_INVALID,
                        message="model_id must not contain path segments.",
                        actual=raw,
                    )
                ]
            },
        )
    return slugify_model_id(raw)


@router.get("/models", response_model=ModelListResponse)
def list_models(request: Request) -> ModelListResponse:
    """List discovered managed models. Incomplete installs are omitted."""
    service = _service(request)
    active_id = _active_id(service)
    models = [
        InstalledModelSchema.from_domain(item, active_id=active_id)
        for item in service.list_models()
    ]
    return ModelListResponse(
        models=models,
        storage=ModelStorageSchema.from_domain(service.storage_status()),
        offline_mode=service.offline_mode,
        active_model_id=active_id,
    )


@router.get("/models/storage", response_model=ModelStorageSchema)
def get_storage(request: Request) -> ModelStorageSchema:
    """Return the configured storage directory and volume free space."""
    return ModelStorageSchema.from_domain(_service(request).storage_status())


@router.put("/models/storage", response_model=ModelStorageSchema)
def update_storage(payload: ModelStorageUpdateRequest, request: Request) -> ModelStorageSchema:
    """Change the primary model-storage directory for this process."""
    storage = _service(request).set_storage_directory(Path(payload.directory))
    return ModelStorageSchema.from_domain(storage)


@router.get("/models/disk-usage", response_model=ModelDiskUsageResponse)
def get_disk_usage(
    request: Request,
    refresh: bool = Query(default=False),
) -> ModelDiskUsageResponse:
    """Return cached per-model sizes. Set refresh=true to walk the filesystem."""
    service = _service(request)
    cached = service.cached_disk_usage()
    if cached is not None and not refresh:
        return ModelDiskUsageResponse.from_domain(cached)
    return ModelDiskUsageResponse.from_domain(service.disk_usage(refresh=refresh))


@router.post("/models/disk-usage/refresh", response_model=ModelDiskUsageResponse)
def refresh_disk_usage(request: Request) -> ModelDiskUsageResponse:
    """Recompute installed-model sizes outside of UI polling loops."""
    return ModelDiskUsageResponse.from_domain(_service(request).disk_usage(refresh=True))


@router.put("/models/offline")
def set_offline(payload: ModelOfflineRequest, request: Request) -> dict[str, bool]:
    """Enable or disable offline mode. Local validated models remain usable."""
    enabled = _service(request).set_offline_mode(payload.enabled)
    return {"offline_mode": enabled}


@router.post("/models/install", response_model=InstalledModelSchema)
def install_model(payload: ModelInstallRequest, request: Request) -> InstalledModelSchema:
    """Copy or download a model into staged storage, then register it if valid."""
    service = _service(request)
    model = service.install(
        source=payload.source,
        identifier=payload.identifier,
        path=payload.path,
        revision=payload.revision,
        display_name=payload.display_name,
        compatibility_manifest=payload.compatibility_manifest,
    )
    return InstalledModelSchema.from_domain(model, active_id=_active_id(service))


@router.get("/models/{model_id}", response_model=InstalledModelSchema)
def get_model(model_id: str, request: Request) -> InstalledModelSchema:
    """Return one managed model."""
    service = _service(request)
    model = service.get_model(_validate_model_id(model_id))
    return InstalledModelSchema.from_domain(model, active_id=_active_id(service))


@router.post("/models/{model_id}/validate", response_model=InstalledModelSchema)
def validate_model(model_id: str, request: Request) -> InstalledModelSchema:
    """Recompute hashes and structure without reinstalling."""
    service = _service(request)
    model = service.revalidate(_validate_model_id(model_id))
    return InstalledModelSchema.from_domain(model, active_id=_active_id(service))


@router.post("/models/{model_id}/activate", response_model=InstalledModelSchema)
def activate_model(model_id: str, request: Request) -> InstalledModelSchema:
    """Select a validated installed model for subsequent generation."""
    service = _service(request)
    model = service.activate(_validate_model_id(model_id))
    return InstalledModelSchema.from_domain(model, active_id=model.id)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: str,
    request: Request,
    confirm: bool = Query(default=False),
) -> None:
    """Delete a managed model after explicit confirmation."""
    _service(request).delete(_validate_model_id(model_id), confirm=confirm)
