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
    transparency_strategy: str = "none"
    alpha_threshold: int | None = None
    alpha_feather: int | None = None
    remove_near_transparent: bool | None = None
    zero_rgb_when_transparent: bool | None = None
    pixels_per_unit: float | None = None
    pivot_mode: str | None = None
    custom_pivot_x: float | None = None
    custom_pivot_y: float | None = None
    atlas_hint: str | None = None
    tileable: bool = False
    apply_seam_correction: bool = False
    seam_blend_width: int | None = None
    palette_reduction_enabled: bool = False
    palette_color_count: int | None = None


@dataclass(frozen=True, slots=True)
class ManifestProfileInfo:
    """Profile provenance recorded without affecting generated parameters."""

    generation_profile_id: str | None = None
    generation_profile_revision: int | None = None
    profile_origin: str = "none"
    prompt_template_id: str | None = None
    prompt_template_revision: int | None = None
    negative_prompt_profile_id: str | None = None
    negative_prompt_profile_revision: int | None = None
    unity_import_profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class ManifestProcessingInfo:
    """Post-inference processing provenance for sprites/icons."""

    transparency_strategy: str
    background_removal_applied: bool
    background_removal_implementation: str | None
    alpha_cleanup_applied: bool
    alpha_threshold: int | None
    alpha_feather: int | None
    remove_near_transparent: bool | None
    zero_rgb_when_transparent: bool | None
    pixels_per_unit: float | None = None
    pivot_mode: str | None = None
    custom_pivot_x: float | None = None
    custom_pivot_y: float | None = None
    atlas_hint: str | None = None
    original_relative_path: str | None = None
    final_relative_path: str | None = None
    tileable: bool = False
    seam_correction_applied: bool = False
    palette_reduction_applied: bool = False
    seam_blend_width: int | None = None
    palette_color_count: int | None = None
    seam_score_before: float | None = None
    seam_score_after: float | None = None
    horizontal_seam_score: float | None = None
    vertical_seam_score: float | None = None
    horizontal_wrap_discontinuity: float | None = None
    vertical_wrap_discontinuity: float | None = None
    seam_inpaint_implementation: str | None = None


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
    profile: ManifestProfileInfo | None = None
    processing: ManifestProcessingInfo | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the public JSON shape."""
        profile = self.profile or ManifestProfileInfo()
        request_payload: dict[str, Any] = {
            "prompt": self.request.prompt,
            "negative_prompt": self.request.negative_prompt,
            "width": self.request.width,
            "height": self.request.height,
            "steps": self.request.steps,
            "guidance_scale": self.request.guidance_scale,
            "seed": self.request.seed,
            "output_name": self.request.output_name,
            "transparency_strategy": self.request.transparency_strategy,
        }
        optional_request = {
            "alpha_threshold": self.request.alpha_threshold,
            "alpha_feather": self.request.alpha_feather,
            "remove_near_transparent": self.request.remove_near_transparent,
            "zero_rgb_when_transparent": self.request.zero_rgb_when_transparent,
            "pixels_per_unit": self.request.pixels_per_unit,
            "pivot_mode": self.request.pivot_mode,
            "custom_pivot_x": self.request.custom_pivot_x,
            "custom_pivot_y": self.request.custom_pivot_y,
            "atlas_hint": self.request.atlas_hint,
            "tileable": self.request.tileable,
            "apply_seam_correction": self.request.apply_seam_correction,
            "seam_blend_width": self.request.seam_blend_width,
            "palette_reduction_enabled": self.request.palette_reduction_enabled,
            "palette_color_count": self.request.palette_color_count,
        }
        for key, value in optional_request.items():
            if value is not None:
                request_payload[key] = value
        # Always echo booleans for tileable controls when present on the request model.
        request_payload["tileable"] = self.request.tileable
        request_payload["apply_seam_correction"] = self.request.apply_seam_correction
        request_payload["palette_reduction_enabled"] = self.request.palette_reduction_enabled

        payload: dict[str, Any] = {
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
            "request": request_payload,
            "profile": {
                "generation_profile_id": profile.generation_profile_id,
                "generation_profile_revision": profile.generation_profile_revision,
                "profile_origin": profile.profile_origin,
                "prompt_template_id": profile.prompt_template_id,
                "prompt_template_revision": profile.prompt_template_revision,
                "negative_prompt_profile_id": profile.negative_prompt_profile_id,
                "negative_prompt_profile_revision": profile.negative_prompt_profile_revision,
                "unity_import_profile_id": profile.unity_import_profile_id,
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
        if self.processing is not None:
            proc = self.processing
            payload["processing"] = {
                "transparency_strategy": proc.transparency_strategy,
                "background_removal_applied": proc.background_removal_applied,
                "background_removal_implementation": proc.background_removal_implementation,
                "alpha_cleanup_applied": proc.alpha_cleanup_applied,
                "alpha_threshold": proc.alpha_threshold,
                "alpha_feather": proc.alpha_feather,
                "remove_near_transparent": proc.remove_near_transparent,
                "zero_rgb_when_transparent": proc.zero_rgb_when_transparent,
                "pixels_per_unit": proc.pixels_per_unit,
                "pivot_mode": proc.pivot_mode,
                "custom_pivot_x": proc.custom_pivot_x,
                "custom_pivot_y": proc.custom_pivot_y,
                "atlas_hint": proc.atlas_hint,
                "original_relative_path": proc.original_relative_path,
                "final_relative_path": proc.final_relative_path,
                "tileable": proc.tileable,
                "seam_correction_applied": proc.seam_correction_applied,
                "palette_reduction_applied": proc.palette_reduction_applied,
                "seam_blend_width": proc.seam_blend_width,
                "palette_color_count": proc.palette_color_count,
                "seam_score_before": proc.seam_score_before,
                "seam_score_after": proc.seam_score_after,
                "horizontal_seam_score": proc.horizontal_seam_score,
                "vertical_seam_score": proc.vertical_seam_score,
                "horizontal_wrap_discontinuity": proc.horizontal_wrap_discontinuity,
                "vertical_wrap_discontinuity": proc.vertical_wrap_discontinuity,
                "seam_inpaint_implementation": proc.seam_inpaint_implementation,
            }
        return payload


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
    Older 1.x manifests without processing blocks remain readable.
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


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _parse_processing(raw: Any) -> ManifestProcessingInfo | None:
    if not isinstance(raw, dict):
        return None
    return ManifestProcessingInfo(
        transparency_strategy=str(raw.get("transparency_strategy") or "none"),
        background_removal_applied=bool(raw.get("background_removal_applied") or False),
        background_removal_implementation=raw.get("background_removal_implementation"),
        alpha_cleanup_applied=bool(raw.get("alpha_cleanup_applied") or False),
        alpha_threshold=_optional_int(raw.get("alpha_threshold")),
        alpha_feather=_optional_int(raw.get("alpha_feather")),
        remove_near_transparent=_optional_bool(raw.get("remove_near_transparent")),
        zero_rgb_when_transparent=_optional_bool(raw.get("zero_rgb_when_transparent")),
        pixels_per_unit=_optional_float(raw.get("pixels_per_unit")),
        pivot_mode=raw.get("pivot_mode"),
        custom_pivot_x=_optional_float(raw.get("custom_pivot_x")),
        custom_pivot_y=_optional_float(raw.get("custom_pivot_y")),
        atlas_hint=raw.get("atlas_hint"),
        original_relative_path=raw.get("original_relative_path"),
        final_relative_path=raw.get("final_relative_path"),
        tileable=bool(raw.get("tileable") or False),
        seam_correction_applied=bool(raw.get("seam_correction_applied") or False),
        palette_reduction_applied=bool(raw.get("palette_reduction_applied") or False),
        seam_blend_width=_optional_int(raw.get("seam_blend_width")),
        palette_color_count=_optional_int(raw.get("palette_color_count")),
        seam_score_before=_optional_float(raw.get("seam_score_before")),
        seam_score_after=_optional_float(raw.get("seam_score_after")),
        horizontal_seam_score=_optional_float(raw.get("horizontal_seam_score")),
        vertical_seam_score=_optional_float(raw.get("vertical_seam_score")),
        horizontal_wrap_discontinuity=_optional_float(raw.get("horizontal_wrap_discontinuity")),
        vertical_wrap_discontinuity=_optional_float(raw.get("vertical_wrap_discontinuity")),
        seam_inpaint_implementation=raw.get("seam_inpaint_implementation"),
    )


def _parse_versioned(payload: dict[str, Any], *, schema_version: str) -> GenerationManifest:
    generation = payload["generation"]
    application = payload["application"]
    model = payload["model"]
    runtime = payload["runtime"]
    request = payload["request"]
    outputs_raw = payload["outputs"]
    profile_raw = payload.get("profile")
    processing = _parse_processing(payload.get("processing"))

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
            transparency_strategy=str(request.get("transparency_strategy") or "none"),
            alpha_threshold=_optional_int(request.get("alpha_threshold")),
            alpha_feather=_optional_int(request.get("alpha_feather")),
            remove_near_transparent=_optional_bool(request.get("remove_near_transparent")),
            zero_rgb_when_transparent=_optional_bool(request.get("zero_rgb_when_transparent")),
            pixels_per_unit=_optional_float(request.get("pixels_per_unit")),
            pivot_mode=request.get("pivot_mode"),
            custom_pivot_x=_optional_float(request.get("custom_pivot_x")),
            custom_pivot_y=_optional_float(request.get("custom_pivot_y")),
            atlas_hint=request.get("atlas_hint"),
            tileable=bool(request.get("tileable") or False),
            apply_seam_correction=bool(request.get("apply_seam_correction") or False),
            seam_blend_width=_optional_int(request.get("seam_blend_width")),
            palette_reduction_enabled=bool(request.get("palette_reduction_enabled") or False),
            palette_color_count=_optional_int(request.get("palette_color_count")),
        ),
        outputs=outputs,
        profile=(
            ManifestProfileInfo()
            if not isinstance(profile_raw, dict)
            else ManifestProfileInfo(
                generation_profile_id=profile_raw.get("generation_profile_id"),
                generation_profile_revision=profile_raw.get("generation_profile_revision"),
                profile_origin=str(profile_raw.get("profile_origin") or "none"),
                prompt_template_id=profile_raw.get("prompt_template_id"),
                prompt_template_revision=profile_raw.get("prompt_template_revision"),
                negative_prompt_profile_id=profile_raw.get("negative_prompt_profile_id"),
                negative_prompt_profile_revision=profile_raw.get(
                    "negative_prompt_profile_revision"
                ),
                unity_import_profile_id=profile_raw.get("unity_import_profile_id"),
            )
        ),
        processing=processing,
    )


def _legacy_to_manifest(payload: dict[str, Any]) -> GenerationManifest:
    """Convert known unversioned flat metadata into the current representation."""
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
        profile=ManifestProfileInfo(),
        processing=None,
    )
