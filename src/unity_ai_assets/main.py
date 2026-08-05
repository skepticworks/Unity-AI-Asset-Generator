"""FastAPI application entrypoint and factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from unity_ai_assets import __version__
from unity_ai_assets.api.routes import generation, health
from unity_ai_assets.core.config import Settings, get_settings
from unity_ai_assets.core.errors import (
    AppError,
    InferenceError,
    InvalidGenerationParametersError,
    ModelLoadError,
    OutputPersistenceError,
)
from unity_ai_assets.core.logging import configure_logging, get_logger
from unity_ai_assets.inference.backend import ImageGenerationBackend
from unity_ai_assets.inference.diffusers_backend import DiffusersBackend
from unity_ai_assets.inference.model_manager import ModelManager
from unity_ai_assets.services.generation_service import GenerationService
from unity_ai_assets.services.output_service import OutputService

logger = get_logger(__name__)

_STATUS_BY_ERROR: dict[type[AppError], int] = {
    InvalidGenerationParametersError: 422,
    ModelLoadError: 503,
    InferenceError: 500,
    OutputPersistenceError: 500,
}


def create_backend(settings: Settings) -> ImageGenerationBackend:
    """Construct the default Diffusers-backed inference engine."""
    manager = ModelManager(settings)
    return DiffusersBackend(manager)


def create_app(
    *,
    settings: Settings | None = None,
    backend: ImageGenerationBackend | None = None,
) -> FastAPI:
    """Application factory supporting dependency injection for tests."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "Starting unity-ai-assets v%s (model_id=%s, device=%s)",
            __version__,
            resolved_settings.model_id,
            resolved_settings.device,
        )
        logger.info(
            "Concurrency: generation requests are serialized with an in-process lock; "
            "run a single Uvicorn worker for this milestone."
        )
        yield
        logger.info("Shutting down unity-ai-assets")

    app = FastAPI(
        title="Unity AI Asset Generator",
        version=__version__,
        description="Local text-to-image texture generation for Unity-ready 2D assets.",
        lifespan=lifespan,
    )

    resolved_backend = backend or create_backend(resolved_settings)
    output_service = OutputService(
        resolved_settings.output_directory,
        app_version=resolved_settings.app_version or __version__,
    )
    generation_service = GenerationService(
        backend=resolved_backend,
        output_service=output_service,
        settings=resolved_settings,
    )

    app.state.settings = resolved_settings
    app.state.generation_service = generation_service

    app.include_router(health.router)
    app.include_router(generation.router)

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        status = _STATUS_BY_ERROR.get(type(exc), 500)
        logger.error("Application error code=%s message=%s", exc.code, exc.message)
        return JSONResponse(
            status_code=status,
            content={
                "error": type(exc).__name__,
                "code": exc.code,
                "message": exc.message,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Avoid leaking internal structure beyond field errors.
        messages: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
            msg = err.get("msg", "invalid value")
            messages.append(f"{loc}: {msg}" if loc else str(msg))
        message = "; ".join(messages) if messages else "Request validation failed"
        return JSONResponse(
            status_code=422,
            content={
                "error": "RequestValidationError",
                "code": "invalid_parameters",
                "message": message,
            },
        )

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
