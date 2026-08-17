"""Health and service-discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from unity_ai_assets.api.schemas.generation import HealthResponse
from unity_ai_assets.core.request_context import get_request_id

router = APIRouter(tags=["health"])


@router.get("/")
def service_root(request: Request) -> JSONResponse:
    """Human/tool service identity (not Chrome DevTools Protocol).

    IDEs and browsers often probe ``GET /`` on localhost ports. Returning a
    small JSON document avoids misleading 404 noise without faking CDP.
    """
    settings = request.app.state.settings
    return JSONResponse(
        {
            "service": "unity-ai-assets",
            "status": "ok",
            "application_version": settings.app_version,
            "endpoints": {
                "health": "/health",
                "ready": "/ready",
                "capabilities": "/api/v1/capabilities",
                "jobs": "/api/v1/jobs",
                "batches": "/api/v1/batches",
                "models": "/api/v1/models",
                "docs": "/docs",
                "openapi": "/openapi.json",
            },
            "request_id": get_request_id(),
        }
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Return lightweight process liveness without loading model weights."""
    settings = request.app.state.settings
    backend = request.app.state.generation_service.backend
    return HealthResponse(
        status="ok",
        application_version=settings.app_version,
        model_loaded=bool(getattr(backend, "model_loaded", False)),
        resolved_device=str(getattr(backend, "device_name", settings.device)),
        request_id=get_request_id(),
    )


@router.get("/ready")
def readiness(request: Request) -> JSONResponse:
    """Report whether configuration, durable paths, queue, and runtime are usable."""
    settings = request.app.state.settings
    runtime = request.app.state.runtime_validator.validate()
    paths = {
        "outputs": settings.output_directory,
        "jobs": settings.job_directory,
        "batches": settings.batch_directory,
        "models": settings.model_storage_directory,
    }
    storage: dict[str, bool] = {}
    for name, path in paths.items():
        assert path is not None
        try:
            path.mkdir(parents=True, exist_ok=True)
            storage[name] = path.is_dir()
        except OSError:
            storage[name] = False
    ready = runtime.usable and all(storage.values()) and request.app.state.job_service.accepting
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "runtime": runtime.to_dict(),
            "storage": storage,
            "job_service_accepting": request.app.state.job_service.accepting,
        },
    )
