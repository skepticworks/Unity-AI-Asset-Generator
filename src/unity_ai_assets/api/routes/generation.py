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
    """Generate a single texture image and persist PNG + versioned manifest."""
    service = request.app.state.generation_service
    result = await asyncio.to_thread(
        service.generate_texture,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        width=payload.width,
        height=payload.height,
        steps=payload.steps,
        guidance_scale=payload.guidance_scale,
        seed=payload.seed,
        output_name=payload.output_name,
        generation_profile_id=payload.generation_profile_id,
        generation_profile_revision=payload.generation_profile_revision,
        profile_origin=payload.profile_origin,
        prompt_template_id=payload.prompt_template_id,
        prompt_template_revision=payload.prompt_template_revision,
        negative_prompt_profile_id=payload.negative_prompt_profile_id,
        negative_prompt_profile_revision=payload.negative_prompt_profile_revision,
        unity_import_profile_id=payload.unity_import_profile_id,
        asset_type=payload.asset_type,
        transparency_strategy=payload.transparency_strategy,
        alpha_threshold=payload.alpha_threshold,
        alpha_feather=payload.alpha_feather,
        remove_near_transparent=payload.remove_near_transparent,
        zero_rgb_when_transparent=payload.zero_rgb_when_transparent,
        pixels_per_unit=payload.pixels_per_unit,
        pivot_mode=payload.pivot_mode,
        custom_pivot_x=payload.custom_pivot_x,
        custom_pivot_y=payload.custom_pivot_y,
        atlas_hint=payload.atlas_hint,
    )
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
            generation_manifest=result.manifest_schema_version,
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
