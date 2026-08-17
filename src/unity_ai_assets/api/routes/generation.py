"""Texture generation and safe artifact retrieval endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from unity_ai_assets.api.schemas.generation import (
    GenerationResources,
    GenerationSchemaVersions,
    TextureGenerationRequest,
    TextureGenerationResponse,
)
from unity_ai_assets.services.output_service import validate_generation_id

router = APIRouter(prefix="/api/v1/generations", tags=["generation"])


def _resources(generation_id: str) -> GenerationResources:
    return GenerationResources(
        image=f"/api/v1/generations/{generation_id}/image",
        manifest=f"/api/v1/generations/{generation_id}/manifest",
    )


@router.post("/textures", response_model=TextureGenerationResponse)
async def generate_texture(
    payload: TextureGenerationRequest,
    request: Request,
) -> TextureGenerationResponse:
    """Submit a generation job and wait for completion (compatibility wrapper).

    GPU work is queued and executed by the local job worker, not inside this
    handler. Unity should prefer ``POST /api/v1/jobs`` and poll for status.
    """
    job_service = request.app.state.job_service
    request.app.state.quota_service.check_queue(job_service)
    record = await asyncio.to_thread(job_service.submit, payload.model_dump(mode="json"))
    record = await asyncio.to_thread(job_service.wait_for_terminal, record.job_id)
    result = job_service.raise_if_unsuccessful(record)
    resources = _resources(result.generation_id)
    return TextureGenerationResponse(
        generation_id=result.generation_id,
        status=result.status,
        operation=result.operation,
        asset_type=result.asset_type,
        seed=result.seed,
        width=result.width,
        height=result.height,
        elapsed_seconds=result.elapsed_seconds,
        resources=resources,
        schema_versions=GenerationSchemaVersions(
            generation_manifest=result.schema_versions.get(
                "generation_manifest", "1.5"
            ),
        ),
        image_path=result.image_path,
        metadata_path=result.metadata_path,
        image_url=resources.image,
        metadata_url=resources.manifest,
    )


@router.get("/{generation_id}/image")
async def get_generation_image(generation_id: str, request: Request) -> FileResponse:
    """Return the PNG for a generation ID (no arbitrary path access)."""
    validate_generation_id(generation_id)
    output_service = request.app.state.output_service
    artifacts = output_service.resolve_artifacts(generation_id)
    return FileResponse(
        path=artifacts.image_path,
        media_type="image/png",
        filename=artifacts.image_path.name,
    )


@router.get("/{generation_id}/manifest")
async def get_generation_manifest(generation_id: str, request: Request) -> JSONResponse:
    """Return the versioned generation manifest."""
    validate_generation_id(generation_id)
    output_service = request.app.state.output_service
    manifest = output_service.load_manifest(generation_id)
    return JSONResponse(content=manifest.to_dict(), media_type="application/json")


@router.get("/{generation_id}/metadata", deprecated=True)
async def get_generation_metadata(generation_id: str, request: Request) -> JSONResponse:
    """Deprecated alias for GET .../manifest. Prefer the manifest endpoint."""
    return await get_generation_manifest(generation_id, request)
