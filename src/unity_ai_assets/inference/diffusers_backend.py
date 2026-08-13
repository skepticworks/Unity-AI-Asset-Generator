"""Diffusers-backed text-to-image implementation."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import torch

from unity_ai_assets.core.errors import (
    GenerationCancelledError,
    InferenceError,
    ModelLoadError,
    OperationUnsupportedError,
)
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.capabilities import InferenceCapabilities
from unity_ai_assets.domain.enums import (
    AssetType,
    OperationType,
    model_family_supports_image_to_image,
    model_family_supports_inpainting,
)
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest
from unity_ai_assets.inference.cancel import pipeline_call_kwargs, raise_if_cancelled
from unity_ai_assets.inference.inpainting import DiffusersInpaintingPipeline
from unity_ai_assets.inference.model_manager import ModelManager

logger = get_logger(__name__)

# Stable public scheduler identifier for the default Stable Diffusion pipeline.
# Selection is not exposed publicly in this milestone.
DEFAULT_PUBLIC_SCHEDULER: str = "pndm"


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
            return self._model_manager.resolve_device_safe()

    def describe_capabilities(self) -> InferenceCapabilities:
        """Report implemented operations without loading model weights."""
        device = self._model_manager.resolve_device_safe()
        precision = self._model_manager.resolve_dtype_name_safe(device)
        available = self._model_manager.available_precision_names(device)
        return InferenceCapabilities(
            text_to_image_supported=True,
            image_to_image_supported=model_family_supports_image_to_image(
                self._model_manager.model_family
            ),
            inpainting_supported=model_family_supports_inpainting(
                self._model_manager.model_family
            ),
            supported_asset_types=[
                AssetType.TEXTURE.value,
                AssetType.SPRITE.value,
                AssetType.ICON.value,
            ],
            scheduler_selection_supported=False,
            default_scheduler=DEFAULT_PUBLIC_SCHEDULER,
            available_schedulers=[],
            available_precisions=available,
            precision_user_selectable=False,
            model_loaded=self._model_manager.is_loaded,
            resolved_device=device,
            resolved_precision=precision,
        )

    def generate(
        self,
        request: GenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
        on_progress: Callable[[str, int | None, int | None], None] | None = None,
    ) -> GeneratedImage:
        raise_if_cancelled(cancel_event)
        operation = request.operation or OperationType.TEXT_TO_IMAGE.value
        if operation == OperationType.INPAINTING.value:
            return DiffusersInpaintingPipeline(self._model_manager).inpaint(
                request, cancel_event=cancel_event, on_progress=on_progress
            )
        if operation == OperationType.IMAGE_TO_IMAGE.value:
            return self._generate_image_to_image(
                request, cancel_event=cancel_event, on_progress=on_progress
            )
        return self._generate_text_to_image(
            request, cancel_event=cancel_event, on_progress=on_progress
        )

    def _generate_text_to_image(
        self,
        request: GenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
        on_progress: Callable[[str, int | None, int | None], None] | None = None,
    ) -> GeneratedImage:
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
        logger.info(
            "Inference starting generation_id=%s size=%sx%s steps=%s guidance=%s device=%s",
            request.generation_id,
            request.width,
            request.height,
            request.steps,
            request.guidance_scale,
            generator_device,
        )
        try:
            # Avoid a tqdm bar that sits at 0% while CUDA is blocked (e.g. Unity using VRAM).
            if hasattr(pipeline, "set_progress_bar_config"):
                pipeline.set_progress_bar_config(disable=True)

            with torch.inference_mode():
                result = pipeline(
                    prompt=request.prompt,
                    negative_prompt=request.negative_prompt or None,
                    width=request.width,
                    height=request.height,
                    num_inference_steps=request.steps,
                    guidance_scale=request.guidance_scale,
                    generator=generator,
                    **pipeline_call_kwargs(
                        cancel_event=cancel_event,
                        on_progress=on_progress,
                        total_steps=request.steps,
                    ),
                )
            image = result.images[0]
        except GenerationCancelledError:
            raise
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inference failed for generation_id=%s", request.generation_id)
            raise InferenceError(
                "Image generation failed. Check prompt parameters, VRAM availability, "
                f"and model compatibility. Details: {type(exc).__name__}"
            ) from exc

        elapsed = time.perf_counter() - started
        logger.info(
            "Inference finished generation_id=%s elapsed=%.2fs",
            request.generation_id,
            elapsed,
        )
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

    def _generate_image_to_image(
        self,
        request: GenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
        on_progress: Callable[[str, int | None, int | None], None] | None = None,
    ) -> GeneratedImage:
        if not model_family_supports_image_to_image(self._model_manager.model_family):
            raise OperationUnsupportedError(
                "The current model does not support image_to_image. "
                "The request was not converted to text-to-image."
            )
        if request.source_image is None:
            raise InferenceError("image_to_image requires a source init image.")

        try:
            txt2img = self._model_manager.get_pipeline()
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelLoadError(
                f"Unexpected failure while obtaining the inference pipeline: {type(exc).__name__}"
            ) from exc

        try:
            from diffusers import AutoPipelineForImage2Image

            pipeline = AutoPipelineForImage2Image.from_pipe(txt2img)
        except Exception as exc:  # noqa: BLE001
            raise OperationUnsupportedError(
                "The loaded model does not support image-to-image generation. "
                "The request was not converted to text-to-image."
            ) from exc

        generator_device = self._model_manager.device
        if generator_device == "cuda":
            generator = torch.Generator(device="cuda").manual_seed(request.seed)
        else:
            generator = torch.Generator(device="cpu").manual_seed(request.seed)

        strength = (
            0.75 if request.denoising_strength is None else float(request.denoising_strength)
        )
        started = time.perf_counter()
        logger.info(
            "Img2img inference starting generation_id=%s size=%sx%s steps=%s guidance=%s "
            "strength=%s device=%s",
            request.generation_id,
            request.width,
            request.height,
            request.steps,
            request.guidance_scale,
            strength,
            generator_device,
        )
        try:
            if hasattr(pipeline, "set_progress_bar_config"):
                pipeline.set_progress_bar_config(disable=True)

            init_image = request.source_image.convert("RGB")
            with torch.inference_mode():
                result = pipeline(
                    prompt=request.prompt,
                    image=init_image,
                    negative_prompt=request.negative_prompt or None,
                    num_inference_steps=request.steps,
                    guidance_scale=request.guidance_scale,
                    strength=strength,
                    generator=generator,
                    **pipeline_call_kwargs(
                        cancel_event=cancel_event,
                        on_progress=on_progress,
                        total_steps=request.steps,
                    ),
                )
            image = result.images[0]
        except GenerationCancelledError:
            raise
        except OperationUnsupportedError:
            raise
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Img2img inference failed for generation_id=%s", request.generation_id)
            raise InferenceError(
                "Image-to-image generation failed. Check the source image, prompt parameters, "
                f"VRAM availability, and model compatibility. Details: {type(exc).__name__}"
            ) from exc

        elapsed = time.perf_counter() - started
        logger.info(
            "Img2img inference finished generation_id=%s elapsed=%.2fs",
            request.generation_id,
            elapsed,
        )
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

    def unload_weights(self) -> bool:
        """Unload the Diffusers txt2img pipeline from VRAM/RAM when loaded."""
        return self._model_manager.unload_pipeline()
