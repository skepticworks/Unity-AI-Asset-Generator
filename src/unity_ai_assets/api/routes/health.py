"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from unity_ai_assets.api.schemas.generation import HealthResponse
from unity_ai_assets.core.request_context import get_request_id

router = APIRouter(tags=["health"])


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
