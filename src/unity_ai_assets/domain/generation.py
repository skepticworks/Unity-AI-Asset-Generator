"""Domain models for image generation (framework-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PIL import Image


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Validated generation parameters used by services and backends."""

    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed: int
    output_name: str
    generation_id: str


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    """In-memory result produced by an inference backend."""

    image: Image.Image
    seed: int
    width: int
    height: int
    elapsed_seconds: float
    device: str
    torch_dtype: str
    model_id: str
    model_revision: str | None


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Persisted generation result returned to API callers."""

    generation_id: str
    status: str
    image_path: str
    metadata_path: str
    seed: int
    width: int
    height: int
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class GenerationMetadata:
    """Reproducibility metadata written beside the PNG."""

    generation_id: str
    created_at_utc: datetime
    model_id: str
    model_revision: str | None
    prompt: str
    negative_prompt: str
    seed: int
    width: int
    height: int
    steps: int
    guidance_scale: float
    device: str
    torch_dtype: str
    app_version: str
    elapsed_seconds: float
    output_filename: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata for JSON persistence."""
        return {
            "generation_id": self.generation_id,
            "created_at_utc": self.created_at_utc.isoformat().replace("+00:00", "Z"),
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "guidance_scale": self.guidance_scale,
            "device": self.device,
            "torch_dtype": self.torch_dtype,
            "app_version": self.app_version,
            "elapsed_seconds": self.elapsed_seconds,
            "output_filename": self.output_filename,
        }
