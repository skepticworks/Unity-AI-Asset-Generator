"""Versioned model compatibility manifests used by capability checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from unity_ai_assets.core.version import (
    MODEL_COMPATIBILITY_SCHEMA_NAME,
    MODEL_COMPATIBILITY_SCHEMA_VERSION,
)
from unity_ai_assets.domain.enums import (
    ModelCompatibilitySchemaStatus,
    ModelFamily,
    OperationType,
    model_family_supports_image_to_image,
    model_family_supports_inpainting,
)

SUPPORTED_COMPATIBILITY_SCHEMA_MAJOR = 1

KNOWN_PIPELINE_CLASSES: dict[str, str] = {
    "StableDiffusionPipeline": ModelFamily.SD15.value,
    "StableDiffusionImg2ImgPipeline": ModelFamily.SD15.value,
    "StableDiffusionInpaintPipeline": ModelFamily.SD15.value,
    "StableDiffusionXLPipeline": ModelFamily.SDXL.value,
    "StableDiffusionXLImg2ImgPipeline": ModelFamily.SDXL.value,
    "StableDiffusionXLInpaintPipeline": ModelFamily.SDXL.value,
}

DEFAULT_REQUIRED_COMPONENTS: tuple[str, ...] = (
    "unet",
    "vae",
    "text_encoder",
    "tokenizer",
    "scheduler",
)


@dataclass(frozen=True, slots=True)
class SchemaVersionParts:
    """Parsed ``major.minor`` schema version."""

    major: int
    minor: int
    raw: str


@dataclass(frozen=True, slots=True)
class ModelCompatibilityManifest:
    """Describes what a managed model can do without loading weights."""

    schema_name: str
    schema_version: str
    schema_status: ModelCompatibilitySchemaStatus
    architecture: str
    pipeline_type: str
    pipeline_class: str | None
    model_family: str
    supported_operations: tuple[str, ...]
    required_components: tuple[str, ...]
    backend_engine: str
    generation_modes: tuple[str, ...]
    notes: str | None = None
    unknown_fields: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_supported_schema(self) -> bool:
        return self.schema_status is ModelCompatibilitySchemaStatus.SUPPORTED

    def supports_operation(self, operation: str) -> bool | None:
        """Return True/False when the manifest lists operations; None if unspecified."""
        if not self.supported_operations:
            return None
        return operation in self.supported_operations

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "architecture": self.architecture,
            "pipeline_type": self.pipeline_type,
            "pipeline_class": self.pipeline_class,
            "model_family": self.model_family,
            "supported_operations": list(self.supported_operations),
            "required_components": list(self.required_components),
            "backend": {"engine": self.backend_engine},
            "generation_modes": list(self.generation_modes),
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


def parse_schema_version(value: object) -> SchemaVersionParts | None:
    """Parse a ``major`` or ``major.minor`` version. Returns None when malformed."""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    parts = raw.split(".")
    if len(parts) > 2:
        return None
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) == 2 else 0
    except ValueError:
        return None
    if major < 0 or minor < 0:
        return None
    return SchemaVersionParts(major=major, minor=minor, raw=raw)


def family_from_pipeline_class(class_name: str | None) -> str:
    """Map a Diffusers pipeline class to the project's model family identifiers."""
    if not class_name:
        return ModelFamily.UNKNOWN.value
    return KNOWN_PIPELINE_CLASSES.get(class_name.strip(), ModelFamily.UNKNOWN.value)


def default_operations_for_family(family: str) -> tuple[str, ...]:
    """Operations implied by the existing family capability helpers."""
    operations = [OperationType.TEXT_TO_IMAGE.value]
    if model_family_supports_image_to_image(family):
        operations.append(OperationType.IMAGE_TO_IMAGE.value)
    if model_family_supports_inpainting(family):
        operations.append(OperationType.INPAINTING.value)
    return tuple(operations)


def pipeline_type_from_class(class_name: str | None) -> str:
    if not class_name:
        return "unknown"
    lowered = class_name.lower()
    if "inpaint" in lowered:
        return "inpaint"
    if "img2img" in lowered:
        return "image_to_image"
    if "xl" in lowered:
        return "stable_diffusion_xl"
    if "stable" in lowered:
        return "stable_diffusion"
    return "unknown"


def build_manifest_from_pipeline(
    *,
    pipeline_class: str | None,
    required_components: tuple[str, ...] | None = None,
    family: str | None = None,
) -> ModelCompatibilityManifest:
    """Create a v1.0 manifest from Diffusers ``model_index.json`` facts."""
    resolved_family = (family or family_from_pipeline_class(pipeline_class)).strip() or (
        ModelFamily.UNKNOWN.value
    )
    operations = default_operations_for_family(resolved_family)
    components = required_components or DEFAULT_REQUIRED_COMPONENTS
    return ModelCompatibilityManifest(
        schema_name=MODEL_COMPATIBILITY_SCHEMA_NAME,
        schema_version=MODEL_COMPATIBILITY_SCHEMA_VERSION,
        schema_status=ModelCompatibilitySchemaStatus.SUPPORTED,
        architecture=resolved_family,
        pipeline_type=pipeline_type_from_class(pipeline_class),
        pipeline_class=pipeline_class,
        model_family=resolved_family,
        supported_operations=operations,
        required_components=tuple(components),
        backend_engine="diffusers",
        generation_modes=operations,
    )


def parse_compatibility_manifest(payload: object) -> ModelCompatibilityManifest:
    """Parse a stored compatibility document. Unknown fields are ignored.

    Newer *minor* versions of schema major 1 are accepted. Newer *major*
    versions are retained with ``unsupported_major`` so callers can list the
    model without treating the manifest as authoritative capability input.
    """
    if not isinstance(payload, dict):
        return ModelCompatibilityManifest(
            schema_name=MODEL_COMPATIBILITY_SCHEMA_NAME,
            schema_version="0",
            schema_status=ModelCompatibilitySchemaStatus.INVALID,
            architecture=ModelFamily.UNKNOWN.value,
            pipeline_type="unknown",
            pipeline_class=None,
            model_family=ModelFamily.UNKNOWN.value,
            supported_operations=(),
            required_components=(),
            backend_engine="diffusers",
            generation_modes=(),
        )

    known_keys = {
        "schema_name",
        "schema_version",
        "architecture",
        "pipeline_type",
        "pipeline_class",
        "model_family",
        "supported_operations",
        "required_components",
        "backend",
        "generation_modes",
        "notes",
    }
    unknown = tuple(sorted(str(key) for key in payload if key not in known_keys))
    version_raw = payload.get("schema_version", MODEL_COMPATIBILITY_SCHEMA_VERSION)
    parsed_version = parse_schema_version(version_raw)
    schema_name = str(payload.get("schema_name") or MODEL_COMPATIBILITY_SCHEMA_NAME)

    if parsed_version is None:
        status = ModelCompatibilitySchemaStatus.INVALID
        version = str(version_raw) if version_raw is not None else "0"
    elif parsed_version.major != SUPPORTED_COMPATIBILITY_SCHEMA_MAJOR:
        status = ModelCompatibilitySchemaStatus.UNSUPPORTED_MAJOR
        version = parsed_version.raw
    else:
        status = ModelCompatibilitySchemaStatus.SUPPORTED
        version = parsed_version.raw

    pipeline_class = _optional_str(payload.get("pipeline_class"))
    family = (
        _optional_str(payload.get("model_family"))
        or _optional_str(payload.get("architecture"))
        or family_from_pipeline_class(pipeline_class)
    )
    operations = _string_tuple(payload.get("supported_operations"))
    modes = _string_tuple(payload.get("generation_modes")) or operations
    components = _string_tuple(payload.get("required_components"))
    backend = payload.get("backend")
    engine = "diffusers"
    if isinstance(backend, dict):
        engine = _optional_str(backend.get("engine")) or engine

    return ModelCompatibilityManifest(
        schema_name=schema_name,
        schema_version=version,
        schema_status=status,
        architecture=_optional_str(payload.get("architecture")) or family,
        pipeline_type=_optional_str(payload.get("pipeline_type"))
        or pipeline_type_from_class(pipeline_class),
        pipeline_class=pipeline_class,
        model_family=family or ModelFamily.UNKNOWN.value,
        supported_operations=operations,
        required_components=components,
        backend_engine=engine,
        generation_modes=modes,
        notes=_optional_str(payload.get("notes")),
        unknown_fields=unknown,
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return tuple(items)
