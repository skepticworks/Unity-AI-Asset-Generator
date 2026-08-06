"""Domain models for versioned capability reporting."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ApiVersionInfo:
    """Public API major/minor version."""

    major: int
    minor: int


@dataclass(frozen=True, slots=True)
class ApplicationIdentity:
    """Application name and semantic version."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class SchemaVersions:
    """Independent schema versions exposed to clients."""

    capabilities: str
    generation_manifest: str


@dataclass(frozen=True, slots=True)
class RuntimeState:
    """Configured versus resolved runtime device/precision and load state."""

    configured_device: str
    resolved_device: str
    configured_precision: str
    resolved_precision: str
    model_loaded: bool


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Configured model identity without requiring weight loading."""

    id: str
    revision: str | None
    family: str
    display_name: str | None


@dataclass(frozen=True, slots=True)
class DimensionConstraints:
    """Width/height limits and multiples for an operation."""

    minimum_width: int
    maximum_width: int
    minimum_height: int
    maximum_height: int
    width_multiple: int
    height_multiple: int
    supported_aspect_ratios: list[str] | None = None


@dataclass(frozen=True, slots=True)
class NumericRangeInt:
    """Integer parameter range with optional default."""

    minimum: int
    maximum: int
    default: int | None = None


@dataclass(frozen=True, slots=True)
class NumericRangeFloat:
    """Float parameter range with optional default."""

    minimum: float
    maximum: float
    default: float | None = None


@dataclass(frozen=True, slots=True)
class SeedConstraints:
    """Seed bounds and random-when-omitted behavior."""

    minimum: int
    maximum: int
    random_when_omitted: bool


@dataclass(frozen=True, slots=True)
class PromptConstraints:
    """Prompt length limit."""

    maximum_length: int


@dataclass(frozen=True, slots=True)
class NegativePromptConstraints:
    """Negative-prompt support and length limit."""

    supported: bool
    maximum_length: int


@dataclass(frozen=True, slots=True)
class OutputNameConstraints:
    """Output basename length limit."""

    maximum_length: int


@dataclass(frozen=True, slots=True)
class SchedulerCapabilities:
    """Scheduler selection behavior and public identifiers."""

    selection_supported: bool
    default: str
    available: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TextToImageCapabilities:
    """Constraints for the text-to-image operation."""

    supported: bool
    asset_types: list[str]
    dimensions: DimensionConstraints
    steps: NumericRangeInt
    guidance_scale: NumericRangeFloat
    seed: SeedConstraints
    prompt: PromptConstraints
    negative_prompt: NegativePromptConstraints
    output_name: OutputNameConstraints
    schedulers: SchedulerCapabilities


@dataclass(frozen=True, slots=True)
class UnsupportedOperation:
    """Minimal declaration for an unimplemented operation."""

    supported: bool = False


@dataclass(frozen=True, slots=True)
class OperationsCapabilities:
    """Per-operation capability declarations."""

    text_to_image: TextToImageCapabilities
    image_to_image: UnsupportedOperation
    inpainting: UnsupportedOperation


@dataclass(frozen=True, slots=True)
class PrecisionCapabilities:
    """Process-level precision reporting."""

    configured: str
    resolved: str
    available: list[str]
    user_selectable: bool


@dataclass(frozen=True, slots=True)
class ConcurrencyLimits:
    """Concurrency limits exposed to clients."""

    maximum_concurrent_generations: int


@dataclass(frozen=True, slots=True)
class CapabilityDocument:
    """Complete versioned capability document (domain form)."""

    api: ApiVersionInfo
    application: ApplicationIdentity
    schemas: SchemaVersions
    runtime: RuntimeState
    model: ModelIdentity
    operations: OperationsCapabilities
    precision: PrecisionCapabilities
    limits: ConcurrencyLimits


@dataclass(frozen=True, slots=True)
class InferenceCapabilities:
    """Capability fragment contributed by an inference backend.

    Must not require loading model weights. Public identifiers only —
    never Diffusers class names.
    """

    text_to_image_supported: bool
    image_to_image_supported: bool
    inpainting_supported: bool
    supported_asset_types: list[str]
    scheduler_selection_supported: bool
    default_scheduler: str
    available_schedulers: list[str]
    available_precisions: list[str]
    precision_user_selectable: bool
    model_loaded: bool
    resolved_device: str
    resolved_precision: str
