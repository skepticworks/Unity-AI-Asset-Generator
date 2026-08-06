"""API route for capability discovery."""

from __future__ import annotations

from fastapi import APIRouter, Request

from unity_ai_assets.api.schemas.capabilities import CapabilitiesResponse

router = APIRouter(prefix="/api/v1", tags=["capabilities"])


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities(request: Request) -> CapabilitiesResponse:
    """Return the versioned capability document.

    Does not load model weights. Describes configured and implemented behavior.
    """
    service = request.app.state.capability_service
    document = service.get_capabilities()
    return CapabilitiesResponse.from_domain(document)
