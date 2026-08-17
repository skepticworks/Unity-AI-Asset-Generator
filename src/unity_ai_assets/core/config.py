"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from unity_ai_assets.core.version import APPLICATION_VERSION
from unity_ai_assets.domain.generation_policy import validate_policy_settings

DeviceChoice = Literal["auto", "cuda", "mps", "cpu"]
TorchDtypeChoice = Literal["auto", "float16", "bfloat16", "float32"]
EnvironmentMode = Literal["local", "production"]
AuthenticationMode = Literal["disabled", "api_key"]
WorkerMode = Literal["local", "remote"]


class Settings(BaseSettings):
    """Runtime settings for model loading, output, and generation policy.

    Environment variables use uppercase names (e.g. MODEL_ID, DEVICE).
    Generation limits here feed the authoritative GenerationPolicy.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    model_id: str = Field(
        default="runwayml/stable-diffusion-v1-5",
        description="Hugging Face Diffusers model identifier",
    )
    model_revision: str | None = Field(default=None)
    model_variant: str | None = Field(default=None)
    model_family: str = Field(
        default="sd15",
        description="Configured model family for capability/manifest reporting",
    )
    model_display_name: str | None = Field(
        default="Stable Diffusion 1.5",
        description="Optional human-readable model label",
    )
    device: DeviceChoice = Field(default="auto")
    torch_dtype: TorchDtypeChoice = Field(default="auto")
    output_directory: Path = Field(default=Path("generated"))
    model_storage_directory: Path = Field(
        default=Path("models"),
        description="Primary directory for managed Diffusers model installs.",
    )
    model_storage_search_paths: tuple[Path, ...] = Field(
        default=(),
        description=(
            "Additional directories scanned for previously installed models "
            "(comma-separated paths in MODEL_STORAGE_SEARCH_PATHS)."
        ),
    )
    offline_mode: bool = Field(
        default=False,
        description=(
            "When true, block network-dependent model-management operations. "
            "Locally installed and validated models remain usable."
        ),
    )
    enable_cpu_offload: bool = Field(default=False)
    exclusive_model_vram: bool = Field(
        default=True,
        description=(
            "When true (and CPU offload is off), keep only one GPU-resident model in VRAM "
            "at a time across txt2img, background removal (rembg), and seam inpaint: unload "
            "post-processing weights before txt2img, unload txt2img before post-processing, "
            "then unload post-processing weights after the request. Preferred on low-VRAM "
            "GPUs when reload cost is acceptable."
        ),
    )
    local_files_only: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    app_version: str = Field(default="")
    environment: EnvironmentMode = Field(default="local")
    bind_host: str = Field(default="127.0.0.1")
    bind_port: int = Field(default=8000, ge=1, le=65535)
    authentication_mode: AuthenticationMode = Field(default="disabled")
    api_key: str | None = Field(default=None, repr=False)
    worker_mode: WorkerMode = Field(default="local")
    remote_worker_url: str | None = Field(default=None)
    remote_worker_token: str | None = Field(default=None, repr=False)
    max_requests_per_minute: int = Field(
        default=0, ge=0, description="0 disables the in-process request-rate limit."
    )
    max_queued_jobs: int = Field(
        default=0, ge=0, description="0 disables the queue-depth limit."
    )

    # Authoritative generation policy (env-configurable)
    min_width: int = Field(default=8, ge=1)
    max_width: int = Field(default=1024, ge=1)
    min_height: int = Field(default=8, ge=1)
    max_height: int = Field(default=1024, ge=1)
    width_multiple: int = Field(default=8, ge=1)
    height_multiple: int = Field(default=8, ge=1)
    min_steps: int = Field(default=1, ge=1)
    max_steps: int = Field(default=150, ge=1)
    default_steps: int = Field(default=25, ge=1)
    min_guidance_scale: float = Field(default=0.0)
    max_guidance_scale: float = Field(default=30.0)
    default_guidance_scale: float = Field(default=7.0)
    min_seed: int = Field(default=0, ge=0)
    max_seed: int = Field(default=2**32 - 1, ge=0)
    max_prompt_length: int = Field(default=2000, ge=1)
    max_negative_prompt_length: int = Field(default=2000, ge=0)
    max_output_name_length: int = Field(default=100, ge=1)
    max_concurrent_generations: int = Field(default=1, ge=1)
    max_job_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum retry attempts after the initial run (0 disables retry).",
    )
    job_auto_retry: bool = Field(
        default=True,
        description="Automatically requeue transient job failures up to max_job_retries.",
    )
    job_directory: Path | None = Field(
        default=None,
        description="Directory for persistent job records. Defaults to {output_directory}/jobs.",
    )
    job_history_limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Default maximum number of jobs returned by history listings.",
    )
    batch_directory: Path | None = Field(
        default=None,
        description="Batch JSON directory. Defaults to {output_directory}/batches.",
    )
    max_batch_jobs: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Maximum number of generation jobs a single batch may expand into.",
    )
    max_batch_prompts: int = Field(
        default=50,
        ge=1,
        le=256,
        description="Maximum prompt entries allowed in a single batch.",
    )
    max_batch_variations: int = Field(
        default=16,
        ge=1,
        le=64,
        description="Maximum variation count per prompt/seed combination.",
    )
    default_scheduler: str = Field(
        default="pndm",
        description="Stable public scheduler identifier used when selection is unsupported",
    )

    # Image-to-image (init/source image). Not reference-image conditioning.
    min_denoising_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    max_denoising_strength: float = Field(default=1.0, ge=0.0, le=1.0)
    default_denoising_strength: float = Field(default=0.75, ge=0.0, le=1.0)
    max_source_image_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        description="Maximum uploaded img2img source-image size in bytes",
    )
    supported_source_image_formats: tuple[str, ...] = Field(
        default=("png", "jpeg", "webp"),
        description="Pillow-normalized img2img source formats (init image, not IP-Adapter)",
    )
    max_mask_image_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        description="Maximum uploaded inpainting mask size in bytes",
    )
    supported_mask_image_formats: tuple[str, ...] = Field(
        default=("png", "jpeg", "webp"),
        description="Pillow-normalized inpainting mask formats (white=inpaint, black=keep)",
    )

    # Optional local background-removal post-processing (sprites/icons)
    background_removal_enabled: bool = Field(
        default=True,
        description=(
            "Enable local rembg-based background removal for sprite/icon workflows. "
            "Requires the optional [background-removal] extra; when rembg is missing, "
            "capabilities report available=false with an install reason."
        ),
    )
    background_removal_backend: str = Field(
        default="rembg",
        description="Background-removal backend identifier (rembg | fake)",
    )
    background_removal_model: str = Field(
        default="u2net",
        description="rembg model name (default u2net); loaded lazily on first use",
    )
    preserve_original_image: bool = Field(
        default=True,
        description="When processing sprites/icons, also persist the pre-processed RGB PNG",
    )

    # Local AI seam inpainting for tileable textures (circular-offset + cross mask)
    seam_inpaint_enabled: bool = Field(
        default=True,
        description="Enable local Diffusers inpainting for tileable seam repair",
    )
    seam_inpaint_model_id: str = Field(
        default="runwayml/stable-diffusion-inpainting",
        description="Hugging Face Diffusers inpaint model (local weights)",
    )
    seam_inpaint_model_revision: str | None = Field(default=None)
    seam_inpaint_steps: int = Field(default=20, ge=1, le=150)
    default_seam_width: int = Field(default=64, ge=8, le=128)

    # Alpha cleanup defaults (authoritative ranges for capability reporting)
    default_alpha_threshold: int = Field(default=16, ge=0, le=255)
    min_alpha_threshold: int = Field(default=0, ge=0, le=255)
    max_alpha_threshold: int = Field(default=255, ge=0, le=255)
    default_alpha_feather: int = Field(default=0, ge=0, le=64)
    min_alpha_feather: int = Field(default=0, ge=0, le=64)
    max_alpha_feather: int = Field(default=64, ge=0, le=64)
    default_remove_near_transparent: bool = Field(default=True)
    default_zero_rgb_when_transparent: bool = Field(default=True)
    default_pixels_per_unit: float = Field(default=100.0, gt=0)
    default_pivot_mode: str = Field(default="center")

    @field_validator(
        "model_revision",
        "model_variant",
        "model_display_name",
        "api_key",
        "remote_worker_url",
        "remote_worker_token",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("job_directory", "batch_directory", mode="before")
    @classmethod
    def _empty_job_dir_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("model_storage_search_paths", mode="before")
    @classmethod
    def _parse_search_paths(cls, value: object) -> object:
        if value is None or value == "":
            return ()
        if isinstance(value, str):
            return tuple(Path(part.strip()) for part in value.split(",") if part.strip())
        if isinstance(value, list | tuple):
            return tuple(Path(str(part)) for part in value if str(part).strip())
        return value

    @field_validator("seam_inpaint_model_revision", mode="before")
    @classmethod
    def _empty_inpaint_revision(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("background_removal_backend", "background_removal_model", mode="before")
    @classmethod
    def _strip_bg_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("default_pivot_mode", mode="before")
    @classmethod
    def _normalize_pivot(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("model_family", mode="before")
    @classmethod
    def _empty_family_to_unknown(cls, value: object) -> object:
        if value is None or value == "":
            return "unknown"
        return value

    @model_validator(mode="after")
    def _validate_policy_and_version(self) -> Self:
        validate_policy_settings(
            min_width=self.min_width,
            max_width=self.max_width,
            min_height=self.min_height,
            max_height=self.max_height,
            width_multiple=self.width_multiple,
            height_multiple=self.height_multiple,
            min_steps=self.min_steps,
            max_steps=self.max_steps,
            default_steps=self.default_steps,
            min_guidance_scale=self.min_guidance_scale,
            max_guidance_scale=self.max_guidance_scale,
            default_guidance_scale=self.default_guidance_scale,
            min_seed=self.min_seed,
            max_seed=self.max_seed,
            max_prompt_length=self.max_prompt_length,
            max_negative_prompt_length=self.max_negative_prompt_length,
            max_output_name_length=self.max_output_name_length,
            max_concurrent_generations=self.max_concurrent_generations,
            min_denoising_strength=self.min_denoising_strength,
            max_denoising_strength=self.max_denoising_strength,
            default_denoising_strength=self.default_denoising_strength,
            max_source_image_bytes=self.max_source_image_bytes,
            max_mask_image_bytes=self.max_mask_image_bytes,
        )
        if not self.app_version:
            object.__setattr__(self, "app_version", APPLICATION_VERSION)
        if self.job_directory is None:
            object.__setattr__(self, "job_directory", self.output_directory / "jobs")
        if self.batch_directory is None:
            object.__setattr__(self, "batch_directory", self.output_directory / "batches")
        if (
            self.environment == "production"
            and self.bind_host not in {"127.0.0.1", "localhost"}
            and self.authentication_mode == "disabled"
        ):
            raise ValueError(
                "AUTHENTICATION_MODE=api_key is required for a production network bind."
            )
        if self.authentication_mode == "api_key" and not self.api_key:
            raise ValueError("API_KEY must be set when AUTHENTICATION_MODE=api_key.")
        if self.worker_mode == "remote" and not self.remote_worker_url:
            raise ValueError("REMOTE_WORKER_URL must be set when WORKER_MODE=remote.")
        return self

    @property
    def resolved_model_family(self) -> str:
        """Configured model family, or unknown when unset."""
        family = (self.model_family or "").strip()
        return family if family else "unknown"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear cached settings (useful in tests)."""
    get_settings.cache_clear()
