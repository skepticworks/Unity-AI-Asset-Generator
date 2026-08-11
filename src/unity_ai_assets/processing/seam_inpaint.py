"""Local AI seam inpainting backends (Diffusers), with fake/unavailable sentinels for tests."""

from __future__ import annotations

import threading
from typing import Any, Protocol

from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.processing.seam_thresholds import (
    DEFAULT_SEAM_INPAINT_NEGATIVE,
    DEFAULT_SEAM_INPAINT_PROMPT,
    TILEABLE_TARGET_SIZE,
)

logger = get_logger(__name__)


class SeamInpainter(Protocol):
    """Local inpainting backend used only for masked seam repair."""

    @property
    def available(self) -> bool: ...

    @property
    def implementation_id(self) -> str: ...

    def inpaint(
        self,
        image: Image.Image,
        mask: Image.Image,
        *,
        prompt: str = DEFAULT_SEAM_INPAINT_PROMPT,
        negative_prompt: str = DEFAULT_SEAM_INPAINT_NEGATIVE,
        steps: int = 20,
        guidance_scale: float = 7.5,
        seed: int | None = None,
    ) -> Image.Image: ...


class UnavailableSeamInpainter:
    """Sentinel when local inpainting is disabled or cannot load."""

    def __init__(self, reason: str = "seam inpainting unavailable") -> None:
        self._reason = reason

    @property
    def available(self) -> bool:
        return False

    @property
    def implementation_id(self) -> str:
        return "unavailable"

    def inpaint(
        self,
        image: Image.Image,
        mask: Image.Image,
        *,
        prompt: str = DEFAULT_SEAM_INPAINT_PROMPT,
        negative_prompt: str = DEFAULT_SEAM_INPAINT_NEGATIVE,
        steps: int = 20,
        guidance_scale: float = 7.5,
        seed: int | None = None,
    ) -> Image.Image:
        raise AppError(
            f"Seam inpainting is unavailable: {self._reason}",
            code=AppErrorCode.SEAM_INPAINT_UNAVAILABLE,
        )


class FakeSeamInpainter:
    """Deterministic test double: fills masked pixels from a soft neighbor average.

    ``fail=True`` keeps the backend *available* but raises on ``inpaint`` so tests can
    distinguish load/config unavailability from inference failure.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    @property
    def available(self) -> bool:
        return True

    @property
    def implementation_id(self) -> str:
        return "fake:neighbor_fill"

    def inpaint(
        self,
        image: Image.Image,
        mask: Image.Image,
        *,
        prompt: str = DEFAULT_SEAM_INPAINT_PROMPT,
        negative_prompt: str = DEFAULT_SEAM_INPAINT_NEGATIVE,
        steps: int = 20,
        guidance_scale: float = 7.5,
        seed: int | None = None,
    ) -> Image.Image:
        if self._fail:
            raise AppError(
                "Fake seam inpainting forced failure.",
                code=AppErrorCode.SEAM_INPAINT_FAILED,
            )
        if image.size != mask.size:
            raise AppError(
                "Inpaint mask size must match image size.",
                code=AppErrorCode.SEAM_INPAINT_FAILED,
            )
        rgba = image.convert("RGBA")
        mask_l = mask.convert("L")
        width, height = rgba.size
        src = list(rgba.getdata())
        mask_px = list(mask_l.getdata())
        out = list(src)

        def sample(x: int, y: int) -> tuple[int, int, int, int]:
            return src[y * width + x]

        for y in range(height):
            for x in range(width):
                idx = y * width + x
                strength = mask_px[idx] / 255.0
                if strength <= 0.0:
                    continue
                # Average unmasked 4-neighborhood; fall back to original if none.
                acc = [0, 0, 0, 0]
                count = 0
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    nidx = ny * width + nx
                    if mask_px[nidx] > 128:
                        continue
                    px = sample(nx, ny)
                    for c in range(4):
                        acc[c] += px[c]
                    count += 1
                if count == 0:
                    continue
                filled = tuple(int(round(acc[c] / count)) for c in range(4))
                orig = src[idx]
                blended = tuple(
                    int(round(orig[c] * (1.0 - strength) + filled[c] * strength)) for c in range(4)
                )
                out[idx] = blended  # type: ignore[assignment]

        result = Image.new("RGBA", (width, height))
        result.putdata(out)
        return result.convert(image.mode) if image.mode != "RGBA" else result


class DiffusersSeamInpainter:
    """Lazy-loaded StableDiffusionInpaintPipeline reused across requests."""

    def __init__(
        self,
        *,
        model_id: str,
        device: str,
        torch_dtype_name: str,
        local_files_only: bool = False,
        enable_cpu_offload: bool = False,
        model_revision: str | None = None,
        steps_default: int = 20,
    ) -> None:
        self._model_id = model_id
        self._device = device
        self._torch_dtype_name = torch_dtype_name
        self._local_files_only = local_files_only
        self._enable_cpu_offload = enable_cpu_offload
        self._model_revision = model_revision
        self._steps_default = steps_default
        self._pipeline: Any | None = None
        self._lock = threading.Lock()
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        if self._load_error is not None and self._pipeline is None:
            return False
        return True

    @property
    def implementation_id(self) -> str:
        return f"diffusers-inpaint:{self._model_id}"

    def _resolve_dtype(self) -> Any:
        import torch

        mapping = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        return mapping.get(self._torch_dtype_name, torch.float32)

    def _ensure_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        with self._lock:
            if self._pipeline is not None:
                return self._pipeline
            try:
                import torch
                from diffusers import StableDiffusionInpaintPipeline
            except ImportError as exc:
                self._load_error = "diffusers/torch not installed"
                raise AppError(
                    "Seam inpainting requires diffusers and torch.",
                    code=AppErrorCode.SEAM_INPAINT_UNAVAILABLE,
                ) from exc

            dtype = self._resolve_dtype()
            load_kwargs: dict[str, Any] = {
                "torch_dtype": dtype,
                "local_files_only": self._local_files_only,
                "safety_checker": None,
                "requires_safety_checker": False,
            }
            if self._model_revision:
                load_kwargs["revision"] = self._model_revision

            logger.info(
                "Loading seam inpaint model %s on %s (%s)",
                self._model_id,
                self._device,
                self._torch_dtype_name,
            )
            try:
                pipeline = StableDiffusionInpaintPipeline.from_pretrained(  # type: ignore[no-untyped-call]
                    self._model_id,
                    **load_kwargs,
                )
                if self._enable_cpu_offload and self._device == "cuda":
                    pipeline.enable_model_cpu_offload()
                else:
                    pipeline = pipeline.to(self._device)
                if hasattr(pipeline, "enable_attention_slicing"):
                    pipeline.enable_attention_slicing()
            except Exception as exc:  # noqa: BLE001
                self._load_error = type(exc).__name__
                raise AppError(
                    "Failed to load the local seam-inpainting model. "
                    f"Details: {type(exc).__name__}",
                    code=AppErrorCode.SEAM_INPAINT_UNAVAILABLE,
                ) from exc

            self._pipeline = pipeline
            return pipeline

    def inpaint(
        self,
        image: Image.Image,
        mask: Image.Image,
        *,
        prompt: str = DEFAULT_SEAM_INPAINT_PROMPT,
        negative_prompt: str = DEFAULT_SEAM_INPAINT_NEGATIVE,
        steps: int = 20,
        guidance_scale: float = 7.5,
        seed: int | None = None,
    ) -> Image.Image:
        import torch

        if image.size != mask.size:
            raise AppError(
                "Inpaint mask size must match image size.",
                code=AppErrorCode.SEAM_INPAINT_FAILED,
            )
        if image.size != (TILEABLE_TARGET_SIZE, TILEABLE_TARGET_SIZE):
            raise AppError(
                f"Seam inpainting requires {TILEABLE_TARGET_SIZE}x{TILEABLE_TARGET_SIZE} images.",
                code=AppErrorCode.SEAM_INPAINT_FAILED,
            )

        try:
            pipeline = self._ensure_pipeline()
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "Seam inpainting model could not be prepared.",
                code=AppErrorCode.SEAM_INPAINT_UNAVAILABLE,
            ) from exc

        rgb = image.convert("RGB")
        mask_rgb = mask.convert("L")
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self._device).manual_seed(int(seed))

        try:
            with torch.inference_mode():
                result = pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    image=rgb,
                    mask_image=mask_rgb,
                    height=TILEABLE_TARGET_SIZE,
                    width=TILEABLE_TARGET_SIZE,
                    num_inference_steps=steps or self._steps_default,
                    guidance_scale=guidance_scale,
                    generator=generator,
                )
            out = result.images[0]
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "Local seam inpainting failed during inference.",
                code=AppErrorCode.SEAM_INPAINT_FAILED,
            ) from exc

        if out.size != (TILEABLE_TARGET_SIZE, TILEABLE_TARGET_SIZE):
            raise AppError(
                "Seam inpainting changed image dimensions.",
                code=AppErrorCode.SEAM_INPAINT_FAILED,
            )
        return out.convert(image.mode) if image.mode != out.mode else out


def create_seam_inpainter(
    *,
    enabled: bool,
    model_id: str,
    device: str,
    torch_dtype_name: str,
    local_files_only: bool = False,
    enable_cpu_offload: bool = False,
    model_revision: str | None = None,
    force_fake: bool = False,
) -> SeamInpainter:
    """Factory mirroring background-removal construction patterns."""
    if force_fake:
        return FakeSeamInpainter()
    if not enabled:
        return UnavailableSeamInpainter(reason="SEAM_INPAINT_ENABLED is false")
    return DiffusersSeamInpainter(
        model_id=model_id,
        device=device,
        torch_dtype_name=torch_dtype_name,
        local_files_only=local_files_only,
        enable_cpu_offload=enable_cpu_offload,
        model_revision=model_revision,
    )
