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
                "capabilities": "/api/v1/capabilities",
                "jobs": "/api/v1/jobs",
                "batches": "/api/v1/batches",
                "docs": "/docs",
                "openapi": "/openapi.json",
            },
            "request_id": get_request_id(),
        }
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Return lightweight process health (not a capability document)."""
    settings = request.app.state.settings
    service = request.app.state.generation_service
    backend = service.backend
    caps = backend.describe_capabilities()
    return HealthResponse(
        status="ok",
        application_version=settings.app_version,
        model_loaded=caps.model_loaded,
        resolved_device=caps.resolved_device,
        request_id=get_request_id(),
    )
