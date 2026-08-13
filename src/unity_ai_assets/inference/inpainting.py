"""Masked inpainting pipeline abstraction.

Inpainting is a first-class generation capability, distinct from text-to-image,
image-to-image (full-frame init variation), and reference-image conditioning.
Shared infrastructure (seeded generators, progress-bar config, GeneratedImage)
is reused; the mask + source alignment and Diffusers inpaint call live here.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

import torch
from PIL import Image

from unity_ai_assets.core.errors import InferenceError, ModelLoadError, OperationUnsupportedError
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.enums import model_family_supports_inpainting
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest
from unity_ai_assets.domain.mask_image import MASK_CONVENTION_ID, prepare_inpaint_mask
from unity_ai_assets.inference.model_manager import ModelManager

logger = get_logger(__name__)


@runtime_checkable
class InpaintingPipeline(Protocol):
    """Contract for masked inpainting runners."""

    def supported(self) -> bool:
        """Whether this pipeline can run inpainting for the configured model."""
        ...

    def inpaint(self, request: GenerationRequest) -> GeneratedImage:
        """Run masked inpainting. Must not fall back to txt2img or img2img."""
        ...


class DiffusersInpaintingPipeline:
    """Inpainting via Diffusers ``AutoPipelineForInpainting.from_pipe``.

    Uses the configured txt2img weights when the family supports inpainting.
    Does not substitute img2img or a different model when from_pipe fails.
    """

    def __init__(self, model_manager: ModelManager) -> None:
        self._model_manager = model_manager

    def supported(self) -> bool:
        return model_family_supports_inpainting(self._model_manager.model_family)

    def inpaint(self, request: GenerationRequest) -> GeneratedImage:
        if not self.supported():
            raise OperationUnsupportedError(
                "The current model does not support inpainting. "
                "The request was not converted to image_to_image or text_to_image."
            )
        if request.source_image is None or request.mask_image is None:
            raise InferenceError("inpainting requires both a source image and a mask.")

        try:
            txt2img = self._model_manager.get_pipeline()
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelLoadError(
                f"Unexpected failure while obtaining the inference pipeline: {type(exc).__name__}"
            ) from exc

        try:
            from diffusers import AutoPipelineForInpainting

            pipeline = AutoPipelineForInpainting.from_pipe(txt2img)
        except Exception as exc:  # noqa: BLE001
            raise OperationUnsupportedError(
                "The loaded model does not support masked inpainting. "
                "The request was not converted to image_to_image or text_to_image."
            ) from exc

        generator_device = self._model_manager.device
        if generator_device == "cuda":
            generator = torch.Generator(device="cuda").manual_seed(request.seed)
        else:
            generator = torch.Generator(device="cpu").manual_seed(request.seed)

        strength = (
            0.75 if request.denoising_strength is None else float(request.denoising_strength)
        )
        init_image = request.source_image.convert("RGB")
        mask_image = prepare_inpaint_mask(request.mask_image, request.width, request.height)
        if init_image.size != (request.width, request.height):
            init_image = init_image.resize(
                (request.width, request.height), Image.Resampling.LANCZOS
            )

        started = time.perf_counter()
        logger.info(
            "Inpainting inference starting generation_id=%s size=%sx%s steps=%s guidance=%s "
            "strength=%s convention=%s device=%s",
            request.generation_id,
            request.width,
            request.height,
            request.steps,
            request.guidance_scale,
            strength,
            request.mask_convention or MASK_CONVENTION_ID,
            generator_device,
        )
        try:
            if hasattr(pipeline, "set_progress_bar_config"):
                pipeline.set_progress_bar_config(disable=True)

            with torch.inference_mode():
                result = pipeline(
                    prompt=request.prompt,
                    image=init_image,
                    mask_image=mask_image,
                    negative_prompt=request.negative_prompt or None,
                    num_inference_steps=request.steps,
                    guidance_scale=request.guidance_scale,
                    strength=strength,
                    generator=generator,
                )
            image = result.images[0]
        except OperationUnsupportedError:
            raise
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Inpainting inference failed for generation_id=%s", request.generation_id
            )
            raise InferenceError(
                "Inpainting failed. Check the source image, mask alignment, prompt "
                "parameters, VRAM availability, and model compatibility. "
                f"Details: {type(exc).__name__}"
            ) from exc

        elapsed = time.perf_counter() - started
        logger.info(
            "Inpainting inference finished generation_id=%s elapsed=%.2fs",
            request.generation_id,
            elapsed,
        )
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        if image.size != (request.width, request.height):
            image = image.resize((request.width, request.height), Image.Resampling.LANCZOS)
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
