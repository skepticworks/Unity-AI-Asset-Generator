"""Domain models for image generation (framework-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass

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
    generation_profile_id: str | None = None
    generation_profile_revision: int | None = None
    profile_origin: str | None = None
    prompt_template_id: str | None = None
    prompt_template_revision: int | None = None
    negative_prompt_profile_id: str | None = None
    negative_prompt_profile_revision: int | None = None
    unity_import_profile_id: str | None = None
    asset_type: str = "texture"


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
    operation: str
    asset_type: str
    image_path: str
    metadata_path: str
    image_url: str
    manifest_url: str
    seed: int
    width: int
    height: int
    elapsed_seconds: float
    manifest_schema_version: str
    image_sha256: str
    image_byte_size: int
