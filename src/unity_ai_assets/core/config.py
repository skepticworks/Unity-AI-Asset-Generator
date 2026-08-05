"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DeviceChoice = Literal["auto", "cuda", "mps", "cpu"]
TorchDtypeChoice = Literal["auto", "float16", "bfloat16", "float32"]


class Settings(BaseSettings):
    """Runtime settings for model loading, output, and limits.

    Environment variables use uppercase names (e.g. MODEL_ID, DEVICE).
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
    device: DeviceChoice = Field(default="auto")
    torch_dtype: TorchDtypeChoice = Field(default="auto")
    output_directory: Path = Field(default=Path("generated"))
    max_width: int = Field(default=1024, ge=8)
    max_height: int = Field(default=1024, ge=8)
    enable_cpu_offload: bool = Field(default=False)
    local_files_only: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    app_version: str = Field(default="0.1.0")

    @field_validator("model_revision", "model_variant", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("max_width", "max_height")
    @classmethod
    def _must_be_divisible_by_eight(cls, value: int) -> int:
        if value % 8 != 0:
            msg = f"Dimension limit {value} must be divisible by 8"
            raise ValueError(msg)
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear cached settings (useful in tests)."""
    get_settings.cache_clear()
