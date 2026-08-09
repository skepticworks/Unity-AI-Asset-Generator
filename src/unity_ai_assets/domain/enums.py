"""Public domain enums for capability and manifest reporting."""

from __future__ import annotations

from enum import StrEnum


class OperationType(StrEnum):
    """Supported and reserved generation operations."""

    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"
    INPAINTING = "inpainting"


class AssetType(StrEnum):
    """Public asset categories produced by generation operations."""

    TEXTURE = "texture"
    SPRITE = "sprite"
    ICON = "icon"
    UI = "ui"


KNOWN_ASSET_TYPES: frozenset[str] = frozenset(item.value for item in AssetType)


def is_known_asset_type(value: str) -> bool:
    """Return whether value is a canonical asset type identifier."""
    return value in KNOWN_ASSET_TYPES


class DeviceType(StrEnum):
    """Configured or resolved inference devices."""

    AUTO = "auto"
    CUDA = "cuda"
    MPS = "mps"
    CPU = "cpu"


class PrecisionType(StrEnum):
    """Configured or resolved numeric precision modes."""

    AUTO = "auto"
    FLOAT16 = "float16"
    BFLOAT16 = "bfloat16"
    FLOAT32 = "float32"


class ModelFamily(StrEnum):
    """Known model families; unknown uses the open string 'unknown'."""

    SD15 = "sd15"
    SDXL = "sdxl"
    UNKNOWN = "unknown"


class GenerationStatus(StrEnum):
    """Lifecycle status recorded in generation manifests."""

    COMPLETED = "completed"
    FAILED = "failed"


class OutputKind(StrEnum):
    """Kinds of persisted generation outputs."""

    IMAGE = "image"
    ORIGINAL_IMAGE = "original_image"


class OutputFormat(StrEnum):
    """Persisted image formats."""

    PNG = "png"


class TransparencyStrategy(StrEnum):
    """How transparent backgrounds are produced for sprites/icons.

    Diffusion models do not natively emit alpha; ``background_removal`` applies
    local post-processing after RGB generation.
    """

    NONE = "none"
    BACKGROUND_REMOVAL = "background_removal"


KNOWN_TRANSPARENCY_STRATEGIES: frozenset[str] = frozenset(
    item.value for item in TransparencyStrategy
)


def is_known_transparency_strategy(value: str) -> bool:
    """Return whether value is a canonical transparency strategy identifier."""
    return value in KNOWN_TRANSPARENCY_STRATEGIES


class PivotMode(StrEnum):
    """Unity sprite pivot modes with stable serialized identifiers."""

    CENTER = "center"
    BOTTOM_CENTER = "bottom_center"
    CUSTOM = "custom"


KNOWN_PIVOT_MODES: frozenset[str] = frozenset(item.value for item in PivotMode)


def is_known_pivot_mode(value: str) -> bool:
    """Return whether value is a canonical pivot mode identifier."""
    return value in KNOWN_PIVOT_MODES
