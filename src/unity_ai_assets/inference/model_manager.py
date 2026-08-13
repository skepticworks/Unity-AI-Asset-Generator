"""Model lifecycle management for Diffusers pipelines."""

from __future__ import annotations

import threading
from typing import Any

import torch

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import ModelLoadError
from unity_ai_assets.core.logging import get_logger

logger = get_logger(__name__)


class ModelManager:
    """Resolve device/dtype and lazily load a reusable Diffusers pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pipeline: Any | None = None
        self._device: str | None = None
        self._dtype: torch.dtype | None = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None

    @property
    def model_id(self) -> str:
        return self._settings.model_id

    @property
    def model_revision(self) -> str | None:
        return self._settings.model_revision

    @property
    def model_family(self) -> str:
        """Configured model family used for capability reporting."""
        return self._settings.resolved_model_family

    @property
    def configured_device(self) -> str:
        """Configured device preference before resolution (auto/cuda/mps/cpu)."""
        return self._settings.device

    @property
    def device(self) -> str:
        if self._device is None:
            self._device = self.resolve_device()
        return self._device

    @property
    def torch_dtype(self) -> torch.dtype:
        if self._dtype is None:
            self._dtype = self.resolve_dtype(self.device)
        return self._dtype

    @property
    def torch_dtype_name(self) -> str:
        return self._dtype_to_name(self.torch_dtype)

    def resolve_device_safe(self) -> str:
        """Resolve device for capability reporting without raising on misconfiguration.

        When an explicitly requested device is unavailable, fall back to the best
        available device rather than failing capability discovery.
        """
        try:
            return self.resolve_device()
        except ModelLoadError:
            if torch.cuda.is_available():
                return "cuda"
            mps = getattr(torch.backends, "mps", None)
            if mps is not None and mps.is_available():
                return "mps"
            return "cpu"

    def resolve_device(self) -> str:
        """Resolve configured device preference to an available torch device."""
        preference = self._settings.device
        if preference == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if (
                getattr(torch.backends, "mps", None) is not None
                and torch.backends.mps.is_available()
            ):
                return "mps"
            return "cpu"

        if preference == "cuda" and not torch.cuda.is_available():
            raise ModelLoadError(
                "DEVICE=cuda was requested but CUDA is not available. "
                "Install a CUDA-enabled PyTorch build or set DEVICE=cpu."
            )
        if preference == "mps":
            mps = getattr(torch.backends, "mps", None)
            if mps is None or not mps.is_available():
                raise ModelLoadError(
                    "DEVICE=mps was requested but Apple MPS is not available on this system."
                )
        return preference

    def resolve_dtype_name_safe(self, device: str) -> str:
        """Resolve a public precision name without loading weights."""
        dtype = self._resolve_dtype_for_device(device, strict=False)
        return self._dtype_to_name(dtype)

    def available_precision_names(self, device: str) -> list[str]:
        """Return precision modes the current implementation can use on this device."""
        available = ["float32"]
        if device in {"cuda", "mps"}:
            available.insert(0, "float16")
        if device == "cuda" and torch.cuda.is_available():
            try:
                if torch.cuda.is_bf16_supported():
                    available.append("bfloat16")
            except Exception:  # noqa: BLE001
                pass
        return available

    def resolve_dtype(self, device: str) -> torch.dtype:
        """Select a safe torch dtype for the resolved device."""
        return self._resolve_dtype_for_device(device, strict=True)

    def _resolve_dtype_for_device(self, device: str, *, strict: bool) -> torch.dtype:
        choice = self._settings.torch_dtype
        if choice == "float16":
            if device == "cpu":
                if strict:
                    raise ModelLoadError(
                        "TORCH_DTYPE=float16 is not supported on CPU. Use float32 or auto."
                    )
                return torch.float32
            return torch.float16
        if choice == "bfloat16":
            return torch.bfloat16
        if choice == "float32":
            return torch.float32

        # auto
        if device == "cuda":
            return torch.float16
        if device == "mps":
            return torch.float16
        return torch.float32

    @staticmethod
    def _dtype_to_name(dtype: torch.dtype) -> str:
        mapping = {
            torch.float16: "float16",
            torch.bfloat16: "bfloat16",
            torch.float32: "float32",
        }
        return mapping.get(dtype, str(dtype).replace("torch.", ""))

    def get_pipeline(self) -> Any:
        """Return a loaded pipeline, loading it once under a lock."""
        if self._pipeline is not None:
            return self._pipeline

        with self._lock:
            if self._pipeline is not None:
                return self._pipeline
            self._pipeline = self._load_pipeline()
            return self._pipeline

    def _load_pipeline(self) -> Any:
        try:
            from diffusers import StableDiffusionPipeline
        except ImportError as exc:
            raise ModelLoadError(
                "diffusers is not installed. Install project dependencies before running inference."
            ) from exc

        device = self.device
        dtype = self.torch_dtype
        settings = self._settings

        logger.info(
            "Loading model %s (revision=%s, variant=%s, device=%s, dtype=%s, local_files_only=%s)",
            settings.model_id,
            settings.model_revision,
            settings.model_variant,
            device,
            self.torch_dtype_name,
            settings.local_files_only,
        )

        load_kwargs: dict[str, Any] = {
            "torch_dtype": dtype,
            "local_files_only": settings.local_files_only,
            "safety_checker": None,
            "requires_safety_checker": False,
        }
        if settings.model_revision:
            load_kwargs["revision"] = settings.model_revision
        if settings.model_variant:
            load_kwargs["variant"] = settings.model_variant

        try:
            # Diffusers stubs are incomplete; treat pipeline construction as Any.
            pipeline = StableDiffusionPipeline.from_pretrained(  # type: ignore[no-untyped-call]
                settings.model_id,
                **load_kwargs,
            )
        except Exception as exc:  # noqa: BLE001 — translated to ModelLoadError
            raise ModelLoadError(
                "Failed to load the configured Diffusers model. "
                "Check MODEL_ID, network access / HF_TOKEN, disk space, and LOCAL_FILES_ONLY. "
                f"Details: {type(exc).__name__}"
            ) from exc

        try:
            if settings.enable_cpu_offload and device == "cuda":
                pipeline.enable_model_cpu_offload()
                logger.info("Enabled model CPU offload for low-VRAM operation")
            else:
                pipeline = pipeline.to(device)

            # Mild memory helpers for consumer GPUs; safe no-ops when unsupported.
            if hasattr(pipeline, "enable_attention_slicing"):
                pipeline.enable_attention_slicing()
        except Exception as exc:  # noqa: BLE001
            raise ModelLoadError(
                f"Model loaded but could not be placed on device '{device}'. "
                f"Details: {type(exc).__name__}"
            ) from exc

        self._device = device
        self._dtype = dtype
        logger.info("Model loaded successfully on %s", device)
        return pipeline

    def unload_pipeline(self) -> bool:
        """Release the txt2img pipeline from memory/VRAM if loaded.

        Returns True when a pipeline was unloaded.
        """
        with self._lock:
            if self._pipeline is None:
                return False
            logger.info("Unloading txt2img pipeline from device to free VRAM")
            pipeline = self._pipeline
            self._pipeline = None
            try:
                del pipeline
            except Exception:  # noqa: BLE001
                pass
            _release_torch_memory(self._device)
            return True


def _release_torch_memory(device: str | None) -> None:
    """Best-effort GC + CUDA cache clear after unloading a pipeline."""
    import gc

    gc.collect()
    if device == "cuda" or (device is None and torch.cuda.is_available()):
        try:
            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass
    mps = getattr(torch.backends, "mps", None)
    if device == "mps" and mps is not None and hasattr(torch, "mps"):
        try:
            empty = getattr(torch.mps, "empty_cache", None)
            if callable(empty):
                empty()
        except Exception:  # noqa: BLE001
            pass
