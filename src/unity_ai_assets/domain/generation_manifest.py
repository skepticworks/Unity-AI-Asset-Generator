"""Versioned generation manifest domain model and legacy compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from unity_ai_assets.core.errors import ManifestSchemaUnsupportedError
from unity_ai_assets.core.version import (
    GENERATION_MANIFEST_SCHEMA_NAME,
    GENERATION_MANIFEST_SCHEMA_VERSION,
)
from unity_ai_assets.domain.enums import (
    AssetType,
    GenerationStatus,
    OperationType,
    OutputFormat,
    OutputKind,
)


@dataclass(frozen=True, slots=True)
class ManifestSchemaInfo:
    """Manifest schema identity."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class ManifestGenerationInfo:
    """Generation lifecycle block."""

    id: str
    operation: str
    asset_type: str
    status: str
    created_at_utc: datetime
    completed_at_utc: datetime
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class ManifestApplicationInfo:
    """Application identity recorded in the manifest."""

    name: str
    version: str
    api_major: int


@dataclass(frozen=True, slots=True)
class ManifestModelInfo:
    """Model identity recorded in the manifest."""

    id: str
    revision: str | None
    family: str


@dataclass(frozen=True, slots=True)
class ManifestRuntimeInfo:
    """Resolved runtime recorded in the manifest."""

    device: str
    precision: str
    scheduler: str


@dataclass(frozen=True, slots=True)
class ManifestRequestInfo:
    """Echo of the generation request parameters actually used."""

    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed: int
    output_name: str


@dataclass(frozen=True, slots=True)
class ManifestOutputInfo:
    """A single persisted output artifact (relative paths only)."""

    kind: str
    format: str
    relative_path: str
    width: int
    height: int
    sha256: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class GenerationManifest:
    """Typed internal representation of a generation manifest."""

    schema: ManifestSchemaInfo
    generation: ManifestGenerationInfo
    application: ManifestApplicationInfo
    model: ManifestModelInfo
    runtime: ManifestRuntimeInfo
    request: ManifestRequestInfo
    outputs: list[ManifestOutputInfo]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the public JSON shape."""
        return {
            "schema": {
                "name": self.schema.name,
                "version": self.schema.version,
            },
            "generation": {
                "id": self.generation.id,
                "operation": self.generation.operation,
                "asset_type": self.generation.asset_type,
                "status": self.generation.status,
                "created_at_utc": _format_utc(self.generation.created_at_utc),
                "completed_at_utc": _format_utc(self.generation.completed_at_utc),
                "elapsed_seconds": self.generation.elapsed_seconds,
            },
            "application": {
                "name": self.application.name,
                "version": self.application.version,
                "api_major": self.application.api_major,
            },
            "model": {
                "id": self.model.id,
                "revision": self.model.revision,
                "family": self.model.family,
            },
            "runtime": {
                "device": self.runtime.device,
                "precision": self.runtime.precision,
                "scheduler": self.runtime.scheduler,
            },
            "request": {
                "prompt": self.request.prompt,
                "negative_prompt": self.request.negative_prompt,
                "width": self.request.width,
                "height": self.request.height,
                "steps": self.request.steps,
                "guidance_scale": self.request.guidance_scale,
                "seed": self.request.seed,
                "output_name": self.request.output_name,
            },
            "outputs": [
                {
                    "kind": output.kind,
                    "format": output.format,
                    "relative_path": output.relative_path,
                    "width": output.width,
                    "height": output.height,
                    "sha256": output.sha256,
                    "byte_size": output.byte_size,
                }
                for output in self.outputs
            ],
        }


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_legacy_metadata(payload: dict[str, Any]) -> bool:
    """Detect the pre-manifest flat metadata format."""
    if "schema" in payload:
        return False
    return "generation_id" in payload and "prompt" in payload and "seed" in payload


def parse_manifest_payload(payload: dict[str, Any]) -> GenerationManifest:
    """Parse a versioned manifest or convert known legacy metadata.

    Unknown versioned formats are rejected. Malformed payloads raise ValueError.
    """
    if is_legacy_metadata(payload):
        return _legacy_to_manifest(payload)

    schema = payload.get("schema")
    if not isinstance(schema, dict):
        raise ValueError("manifest schema block is missing")
    name = schema.get("name")
    version = schema.get("version")
    if name != GENERATION_MANIFEST_SCHEMA_NAME:
        raise ManifestSchemaUnsupportedError(f"Unsupported manifest schema name '{name}'.")
    if not isinstance(version, str) or not version:
        raise ManifestSchemaUnsupportedError("Manifest schema version is missing.")
    major = version.split(".", maxsplit=1)[0]
    supported_major = GENERATION_MANIFEST_SCHEMA_VERSION.split(".", maxsplit=1)[0]
    if major != supported_major:
        raise ManifestSchemaUnsupportedError(f"Unsupported manifest schema version '{version}'.")

    try:
        return _parse_versioned(payload, schema_version=version)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Malformed generation manifest: {exc}") from exc


def _parse_versioned(payload: dict[str, Any], *, schema_version: str) -> GenerationManifest:
    generation = payload["generation"]
    application = payload["application"]
    model = payload["model"]
    runtime = payload["runtime"]
    request = payload["request"]
    outputs_raw = payload["outputs"]

    created = _parse_utc(generation["created_at_utc"])
    completed = _parse_utc(generation["completed_at_utc"])
    if created is None or completed is None:
        raise ValueError("invalid timestamps")

    outputs = [
        ManifestOutputInfo(
            kind=str(item["kind"]),
            format=str(item["format"]),
            relative_path=str(item["relative_path"]),
            width=int(item["width"]),
            height=int(item["height"]),
            sha256=str(item["sha256"]),
            byte_size=int(item["byte_size"]),
        )
        for item in outputs_raw
    ]

    return GenerationManifest(
        schema=ManifestSchemaInfo(
            name=GENERATION_MANIFEST_SCHEMA_NAME,
            version=schema_version,
        ),
        generation=ManifestGenerationInfo(
            id=str(generation["id"]),
            operation=str(generation["operation"]),
            asset_type=str(generation["asset_type"]),
            status=str(generation["status"]),
            created_at_utc=created,
            completed_at_utc=completed,
            elapsed_seconds=float(generation["elapsed_seconds"]),
        ),
        application=ManifestApplicationInfo(
            name=str(application["name"]),
            version=str(application["version"]),
            api_major=int(application["api_major"]),
        ),
        model=ManifestModelInfo(
            id=str(model["id"]),
            revision=model.get("revision"),
            family=str(model["family"]),
        ),
        runtime=ManifestRuntimeInfo(
            device=str(runtime["device"]),
            precision=str(runtime["precision"]),
            scheduler=str(runtime["scheduler"]),
        ),
        request=ManifestRequestInfo(
            prompt=str(request["prompt"]),
            negative_prompt=str(request.get("negative_prompt") or ""),
            width=int(request["width"]),
            height=int(request["height"]),
            steps=int(request["steps"]),
            guidance_scale=float(request["guidance_scale"]),
            seed=int(request["seed"]),
            output_name=str(request["output_name"]),
        ),
        outputs=outputs,
    )


def _legacy_to_manifest(payload: dict[str, Any]) -> GenerationManifest:
    """Convert known unversioned flat metadata into the current representation.

    Fields that cannot be reconstructed from legacy metadata are set to null
    (revision already nullable) or documented defaults:
    - schema is synthesized as generation-manifest 1.0
    - operation defaults to text_to_image
    - asset_type defaults to texture
    - status defaults to completed
    - completed_at_utc mirrors created_at_utc when absent
    - application.name defaults to unity-ai-asset-generator
    - application.api_major defaults to 1
    - model.family defaults to unknown
    - runtime.scheduler defaults to unknown
    - outputs[].sha256 and byte_size are null-equivalent empty/0 when absent
    - output relative_path uses output_filename when present
    """
    created = _parse_utc(payload.get("created_at_utc")) or datetime.now(UTC)
    output_filename = str(payload.get("output_filename") or "texture.png")
    output_name = output_filename.rsplit(".", maxsplit=1)[0]
    sha256 = payload.get("sha256")
    byte_size = payload.get("byte_size")

    return GenerationManifest(
        schema=ManifestSchemaInfo(
            name=GENERATION_MANIFEST_SCHEMA_NAME,
            version=GENERATION_MANIFEST_SCHEMA_VERSION,
        ),
        generation=ManifestGenerationInfo(
            id=str(payload["generation_id"]),
            operation=OperationType.TEXT_TO_IMAGE.value,
            asset_type=AssetType.TEXTURE.value,
            status=GenerationStatus.COMPLETED.value,
            created_at_utc=created,
            completed_at_utc=created,
            elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
        ),
        application=ManifestApplicationInfo(
            name=str(payload.get("application_name") or "unity-ai-asset-generator"),
            version=str(payload.get("app_version") or "0.0.0"),
            api_major=int(payload.get("api_major") or 1),
        ),
        model=ManifestModelInfo(
            id=str(payload.get("model_id") or "unknown"),
            revision=payload.get("model_revision"),
            family=str(payload.get("model_family") or "unknown"),
        ),
        runtime=ManifestRuntimeInfo(
            device=str(payload.get("device") or "unknown"),
            precision=str(payload.get("torch_dtype") or payload.get("precision") or "unknown"),
            scheduler=str(payload.get("scheduler") or "unknown"),
        ),
        request=ManifestRequestInfo(
            prompt=str(payload.get("prompt") or ""),
            negative_prompt=str(payload.get("negative_prompt") or ""),
            width=int(payload.get("width") or 0),
            height=int(payload.get("height") or 0),
            steps=int(payload.get("steps") or 0),
            guidance_scale=float(payload.get("guidance_scale") or 0.0),
            seed=int(payload.get("seed") or 0),
            output_name=output_name,
        ),
        outputs=[
            ManifestOutputInfo(
                kind=OutputKind.IMAGE.value,
                format=OutputFormat.PNG.value,
                relative_path=output_filename,
                width=int(payload.get("width") or 0),
                height=int(payload.get("height") or 0),
                sha256=str(sha256) if sha256 else "",
                byte_size=int(byte_size) if byte_size is not None else 0,
            )
        ],
    )
