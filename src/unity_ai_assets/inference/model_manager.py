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
        dtype = self.torch_dtype
        mapping = {
            torch.float16: "float16",
            torch.bfloat16: "bfloat16",
            torch.float32: "float32",
        }
        return mapping.get(dtype, str(dtype).replace("torch.", ""))

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

    def resolve_dtype(self, device: str) -> torch.dtype:
        """Select a safe torch dtype for the resolved device."""
        choice = self._settings.torch_dtype
        if choice == "float16":
            if device == "cpu":
                raise ModelLoadError(
                    "TORCH_DTYPE=float16 is not supported on CPU. Use float32 or auto."
                )
            return torch.float16
        if choice == "bfloat16":
            if device == "cpu" and not torch.cuda.is_bf16_supported():
                # CPU bf16 support varies; prefer explicit user choice when set.
                return torch.bfloat16
            return torch.bfloat16
        if choice == "float32":
            return torch.float32

        # auto
        if device == "cuda":
            return torch.float16
        # MPS float16 is commonly usable; fall back to float32 if issues arise at runtime.
        if device == "mps":
            return torch.float16
        return torch.float32

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
