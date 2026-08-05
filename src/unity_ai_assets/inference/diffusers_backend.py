"""Diffusers-backed text-to-image implementation."""

from __future__ import annotations

import time

import torch

from unity_ai_assets.core.errors import InferenceError, ModelLoadError
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest
from unity_ai_assets.inference.model_manager import ModelManager

logger = get_logger(__name__)


class DiffusersBackend:
    """ImageGenerationBackend implementation using Hugging Face Diffusers."""

    def __init__(self, model_manager: ModelManager) -> None:
        self._model_manager = model_manager

    @property
    def model_loaded(self) -> bool:
        return self._model_manager.is_loaded

    @property
    def device_name(self) -> str:
        try:
            return self._model_manager.device
        except ModelLoadError:
            return self._model_manager.configured_device

    def generate(self, request: GenerationRequest) -> GeneratedImage:
        try:
            pipeline = self._model_manager.get_pipeline()
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelLoadError(
                f"Unexpected failure while obtaining the inference pipeline: {type(exc).__name__}"
            ) from exc

        generator_device = self._model_manager.device
        # CUDA generators must live on GPU; MPS/CPU use CPU generator for stability.
        if generator_device == "cuda":
            generator = torch.Generator(device="cuda").manual_seed(request.seed)
        else:
            generator = torch.Generator(device="cpu").manual_seed(request.seed)

        started = time.perf_counter()
        try:
            with torch.inference_mode():
                result = pipeline(
                    prompt=request.prompt,
                    negative_prompt=request.negative_prompt or None,
                    width=request.width,
                    height=request.height,
                    num_inference_steps=request.steps,
                    guidance_scale=request.guidance_scale,
                    generator=generator,
                )
            image = result.images[0]
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inference failed for generation_id=%s", request.generation_id)
            raise InferenceError(
                "Image generation failed. Check prompt parameters, VRAM availability, "
                f"and model compatibility. Details: {type(exc).__name__}"
            ) from exc

        elapsed = time.perf_counter() - started
        return GeneratedImage(
            image=image,
            seed=request.seed,
            width=request.width,
            height=request.height,
            elapsed_seconds=round(elapsed, 4),
            device=self._model_manager.device,
            torch_dtype=self._model_manager.torch_dtype_name,
            model_id=self._model_manager.model_id,
            model_revision=self._model_manager.model_revision,
        )
