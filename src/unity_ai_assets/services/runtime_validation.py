"""Structured, inexpensive runtime and accelerator diagnostics."""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from unity_ai_assets.core.config import Settings
from unity_ai_assets.inference.model_manager import ModelManager

SD15_RECOMMENDED_VRAM_BYTES = 4 * 1024 * 1024 * 1024
SDXL_RECOMMENDED_VRAM_BYTES = 8 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class RuntimeCheck:
    name: str
    status: str  # ok | warning | fatal | insufficient_resources
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeValidationReport:
    selected_device: str | None
    usable: bool
    checks: list[RuntimeCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_device": self.selected_device,
            "usable": self.usable,
            "checks": [asdict(check) for check in self.checks],
        }


@dataclass(frozen=True)
class HardwareSnapshot:
    """Observable accelerator facts. Tests inject this instead of real GPU queries."""

    cuda_available: bool = False
    cuda_version: str | None = None
    device_name: str | None = None
    total_vram_bytes: int | None = None
    accelerate_present: bool = False
    vram_error: str | None = None


class HardwareProbe(Protocol):
    def snapshot(self) -> HardwareSnapshot: ...


class TorchHardwareProbe:
    """Read Torch/CUDA facts without loading model weights."""

    def snapshot(self) -> HardwareSnapshot:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        cuda_version = getattr(torch.version, "cuda", None)
        device_name: str | None = None
        total_vram_bytes: int | None = None
        vram_error: str | None = None
        if cuda_available:
            try:
                properties = torch.cuda.get_device_properties(0)
                device_name = properties.name
                total_vram_bytes = int(properties.total_memory)
            except Exception as exc:  # pragma: no cover - driver-specific
                vram_error = str(exc)
        return HardwareSnapshot(
            cuda_available=cuda_available,
            cuda_version=cuda_version,
            device_name=device_name,
            total_vram_bytes=total_vram_bytes,
            accelerate_present=importlib.util.find_spec("accelerate") is not None,
            vram_error=vram_error,
        )


class RuntimeValidator:
    """Inspect Torch, configuration, and model manifests without loading weights."""

    def __init__(
        self,
        settings: Settings,
        *,
        probe: HardwareProbe | None = None,
        model_service: Any | None = None,
    ) -> None:
        self._settings = settings
        self._probe = probe or TorchHardwareProbe()
        self._model_service = model_service

    def validate(self) -> RuntimeValidationReport:
        checks: list[RuntimeCheck] = []
        hardware = self._probe.snapshot()
        manager = ModelManager(self._settings)
        selected_device: str | None
        try:
            selected_device = manager.resolve_device()
            checks.append(RuntimeCheck("device_selection", "ok", f"Selected {selected_device}."))
        except Exception as exc:
            selected_device = None
            checks.append(RuntimeCheck("device_selection", "fatal", str(exc)))

        checks.append(
            RuntimeCheck(
                "cuda",
                "ok" if hardware.cuda_available else "warning",
                (
                    "CUDA is available."
                    if hardware.cuda_available
                    else "CUDA acceleration is unavailable."
                ),
                {"torch_cuda_version": hardware.cuda_version},
            )
        )
        if hardware.cuda_available:
            if hardware.vram_error:
                checks.append(
                    RuntimeCheck(
                        "vram",
                        "warning",
                        f"Could not inspect VRAM: {hardware.vram_error}",
                    )
                )
            else:
                checks.append(
                    RuntimeCheck(
                        "vram",
                        "ok",
                        "GPU memory detected.",
                        {
                            "device_name": hardware.device_name,
                            "total_vram_bytes": hardware.total_vram_bytes,
                        },
                    )
                )
        checks.append(
            RuntimeCheck(
                "accelerate",
                "ok" if hardware.accelerate_present else "warning",
                (
                    "accelerate is installed."
                    if hardware.accelerate_present
                    else "accelerate is not installed."
                ),
            )
        )
        if self._settings.enable_cpu_offload and not hardware.accelerate_present:
            checks.append(
                RuntimeCheck(
                    "cpu_offload",
                    "fatal",
                    "ENABLE_CPU_OFFLOAD requires the accelerate package.",
                )
            )
        if selected_device is not None:
            checks.append(
                RuntimeCheck(
                    "framework_precision",
                    "ok",
                    f"Resolved dtype {manager.resolve_dtype_name_safe(selected_device)}.",
                )
            )
        checks.extend(self._model_compatibility_checks(selected_device, hardware))
        return RuntimeValidationReport(
            selected_device=selected_device,
            usable=not any(check.status == "fatal" for check in checks),
            checks=checks,
        )

    def _model_compatibility_checks(
        self,
        selected_device: str | None,
        hardware: HardwareSnapshot,
    ) -> list[RuntimeCheck]:
        if self._model_service is None:
            return []
        get_active = getattr(self._model_service, "get_active", None)
        if get_active is None:
            return []
        active = get_active()
        if active is None:
            return [
                RuntimeCheck(
                    "active_model",
                    "warning",
                    "No managed model is active; generation uses MODEL_ID if available.",
                )
            ]
        details = {
            "model_id": getattr(active, "id", None),
            "family": getattr(active, "family", None),
            "usable": bool(getattr(active, "is_usable", False)),
        }
        checks = [
            RuntimeCheck(
                "active_model",
                "ok" if getattr(active, "is_usable", False) else "warning",
                (
                    f"Active model '{active.id}' is usable."
                    if getattr(active, "is_usable", False)
                    else f"Active model '{active.id}' is not currently usable."
                ),
                details,
            )
        ]
        compatibility = getattr(active, "compatibility", None)
        if compatibility is None:
            checks.append(
                RuntimeCheck(
                    "model_compatibility",
                    "warning",
                    "Active model has no compatibility manifest.",
                    details,
                )
            )
            return checks
        if not compatibility.is_supported_schema:
            checks.append(
                RuntimeCheck(
                    "model_compatibility",
                    "warning",
                    "Active model compatibility schema is not applied to capability checks.",
                    {**details, "schema_status": str(compatibility.schema_status)},
                )
            )
        else:
            checks.append(
                RuntimeCheck(
                    "model_compatibility",
                    "ok",
                    "Active model compatibility manifest is supported.",
                    {
                        **details,
                        "pipeline_class": compatibility.pipeline_class,
                        "supported_operations": list(compatibility.supported_operations),
                    },
                )
            )
        family = (compatibility.model_family or getattr(active, "family", "") or "").lower()
        recommended = (
            SDXL_RECOMMENDED_VRAM_BYTES if family == "sdxl" else SD15_RECOMMENDED_VRAM_BYTES
        )
        if selected_device == "cpu" and family in {"sd15", "sdxl"}:
            checks.append(
                RuntimeCheck(
                    "model_resources",
                    "insufficient_resources",
                    f"Active {family} model is selected on CPU; "
                    "generation will be slow or impractical.",
                    {**details, "selected_device": selected_device},
                )
            )
        elif (
            hardware.total_vram_bytes is not None
            and hardware.total_vram_bytes < recommended
            and selected_device == "cuda"
        ):
            checks.append(
                RuntimeCheck(
                    "model_resources",
                    "insufficient_resources",
                    (
                        f"Detected VRAM is below the recommended size for family '{family}'. "
                        "The model may fail to load."
                    ),
                    {
                        **details,
                        "total_vram_bytes": hardware.total_vram_bytes,
                        "recommended_vram_bytes": recommended,
                    },
                )
            )
        return checks
