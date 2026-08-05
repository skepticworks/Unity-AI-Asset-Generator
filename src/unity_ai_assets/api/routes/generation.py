"""Texture generation endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from unity_ai_assets.api.schemas.generation import (
    TextureGenerationRequest,
    TextureGenerationResponse,
)

router = APIRouter(prefix="/api/v1/generations", tags=["generation"])


@router.post("/textures", response_model=TextureGenerationResponse)
async def generate_texture(
    payload: TextureGenerationRequest,
    request: Request,
) -> TextureGenerationResponse:
    """Generate a single texture image and persist PNG + metadata.

    The underlying Diffusers call is synchronous and serialized with an
    application-level lock. This handler awaits that work on a worker thread
    so the event loop is not blocked for the entire diffusion duration.
    """
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
    )
    return TextureGenerationResponse(
        generation_id=result.generation_id,
        status=result.status,
        image_path=result.image_path,
        metadata_path=result.metadata_path,
        seed=result.seed,
        width=result.width,
        height=result.height,
        elapsed_seconds=result.elapsed_seconds,
    )
