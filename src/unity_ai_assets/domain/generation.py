"""Domain models for image generation (framework-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.domain.enums import OperationType


@dataclass(frozen=True, slots=True)
class SourceImageMetadata:
    """Provenance for an img2img init/source image (pixels are not persisted).

    This describes the uploaded init image used as the generation latent starting
    point. It is not a reference-conditioning (IP-Adapter) descriptor.
    """

    format: str
    media_type: str
    original_width: int
    original_height: int
    byte_size: int
    sha256: str


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
    transparency_strategy: str = "none"
    alpha_threshold: int = 16
    alpha_feather: int = 0
    remove_near_transparent: bool = True
    zero_rgb_when_transparent: bool = True
    pixels_per_unit: float | None = None
    pivot_mode: str | None = None
    custom_pivot_x: float | None = None
    custom_pivot_y: float | None = None
    atlas_hint: str | None = None
    tileable: bool = False
    apply_seam_correction: bool = False
    seam_blend_width: int = 64
    palette_reduction_enabled: bool = False
    palette_color_count: int = 16
    operation: str = OperationType.TEXT_TO_IMAGE.value
    denoising_strength: float | None = None
    source_image: Image.Image | None = None
    source_image_meta: SourceImageMetadata | None = None
    mask_image: Image.Image | None = None
    mask_image_meta: SourceImageMetadata | None = None
    mask_convention: str | None = None


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
