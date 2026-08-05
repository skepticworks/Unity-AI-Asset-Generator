"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from unity_ai_assets.api.schemas.generation import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Return process health and model load state."""
    service = request.app.state.generation_service
    backend = service.backend
    return HealthResponse(
        status="ok",
        model_loaded=backend.model_loaded,
        device=backend.device_name,
    )
