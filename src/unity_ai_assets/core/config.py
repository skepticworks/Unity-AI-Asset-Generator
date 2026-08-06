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
    enable_cpu_offload: bool = Field(default=False)
    local_files_only: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    app_version: str = Field(default="")

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
    default_scheduler: str = Field(
        default="pndm",
        description="Stable public scheduler identifier used when selection is unsupported",
    )

    @field_validator("model_revision", "model_variant", "model_display_name", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
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
        )
        if not self.app_version:
            object.__setattr__(self, "app_version", APPLICATION_VERSION)
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
