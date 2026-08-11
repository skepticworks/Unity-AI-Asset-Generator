"""FastAPI application entrypoint and factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from unity_ai_assets.api.routes import capabilities, generation, health
from unity_ai_assets.core.config import Settings, get_settings
from unity_ai_assets.core.exception_handlers import register_exception_handlers
from unity_ai_assets.core.logging import configure_logging, get_logger
from unity_ai_assets.core.middleware import RequestIdMiddleware
from unity_ai_assets.core.version import APPLICATION_VERSION
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.inference.backend import ImageGenerationBackend
from unity_ai_assets.inference.diffusers_backend import DiffusersBackend
from unity_ai_assets.inference.model_manager import ModelManager
from unity_ai_assets.processing.background_removal import create_background_remover
from unity_ai_assets.processing.pipeline import ImageProcessingPipeline
from unity_ai_assets.processing.seam_inpaint import create_seam_inpainter
from unity_ai_assets.services.capability_service import CapabilityService
from unity_ai_assets.services.generation_service import GenerationService
from unity_ai_assets.services.output_service import OutputService

logger = get_logger(__name__)


def create_backend(settings: Settings) -> ImageGenerationBackend:
    """Construct the default Diffusers-backed inference engine."""
    manager = ModelManager(settings)
    return DiffusersBackend(manager)


def create_app(
    *,
    settings: Settings | None = None,
    backend: ImageGenerationBackend | None = None,
    force_fake_background_removal: bool = False,
    force_fake_seam_inpaint: bool = False,
) -> FastAPI:
    """Application factory supporting dependency injection for tests."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    policy = GenerationPolicy.from_settings(resolved_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "Starting unity-ai-assets v%s (model_id=%s, device=%s)",
            resolved_settings.app_version or APPLICATION_VERSION,
            resolved_settings.model_id,
            resolved_settings.device,
        )
        logger.info(
            "Concurrency: generation requests are serialized with an in-process lock; "
            "run a single Uvicorn worker for this milestone."
        )
        logger.info(
            "Background removal enabled=%s backend=%s model=%s",
            resolved_settings.background_removal_enabled,
            resolved_settings.background_removal_backend,
            resolved_settings.background_removal_model,
        )
        logger.info(
            "Seam inpaint enabled=%s model=%s",
            resolved_settings.seam_inpaint_enabled,
            resolved_settings.seam_inpaint_model_id,
        )
        yield
        logger.info("Shutting down unity-ai-assets")

    app = FastAPI(
        title="Unity AI Asset Generator",
        version=resolved_settings.app_version or APPLICATION_VERSION,
        description=(
            "Local text-to-image generation for Unity-ready 2D textures, sprites, and icons."
        ),
        lifespan=lifespan,
    )

    resolved_backend = backend or create_backend(resolved_settings)
    background_remover = create_background_remover(
        enabled=resolved_settings.background_removal_enabled,
        backend=resolved_settings.background_removal_backend,
        model=resolved_settings.background_removal_model,
        force_fake=force_fake_background_removal,
    )

    # Resolve device/dtype for inpaint without forcing txt2img weights to load.
    device_manager = ModelManager(resolved_settings)
    inpaint_device = device_manager.resolve_device_safe()
    inpaint_dtype = device_manager.resolve_dtype_name_safe(inpaint_device)

    seam_inpainter = create_seam_inpainter(
        enabled=resolved_settings.seam_inpaint_enabled,
        model_id=resolved_settings.seam_inpaint_model_id,
        device=inpaint_device,
        torch_dtype_name=inpaint_dtype,
        local_files_only=resolved_settings.local_files_only,
        enable_cpu_offload=resolved_settings.enable_cpu_offload,
        model_revision=resolved_settings.seam_inpaint_model_revision,
        force_fake=force_fake_seam_inpaint,
    )
    processing_pipeline = ImageProcessingPipeline(background_remover, seam_inpainter)
    output_service = OutputService(
        resolved_settings.output_directory,
        app_version=resolved_settings.app_version or APPLICATION_VERSION,
        model_family=resolved_settings.resolved_model_family,
        default_scheduler=resolved_settings.default_scheduler,
        max_output_name_length=resolved_settings.max_output_name_length,
    )
    generation_service = GenerationService(
        backend=resolved_backend,
        output_service=output_service,
        settings=resolved_settings,
        policy=policy,
        processing_pipeline=processing_pipeline,
    )
    capability_service = CapabilityService(
        settings=resolved_settings,
        policy=policy,
        backend=resolved_backend,
        background_remover=background_remover,
        seam_inpainter=seam_inpainter,
    )

    app.state.settings = resolved_settings
    app.state.generation_policy = policy
    app.state.generation_service = generation_service
    app.state.output_service = output_service
    app.state.capability_service = capability_service
    app.state.background_remover = background_remover
    app.state.seam_inpainter = seam_inpainter
    app.state.processing_pipeline = processing_pipeline

    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(capabilities.router)
    app.include_router(generation.router)

    return app


app = create_app()


def run() -> None:
    """CLI entrypoint for `unity-ai-assets` / `python -m unity_ai_assets.main`."""
    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "unity_ai_assets.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    run()
