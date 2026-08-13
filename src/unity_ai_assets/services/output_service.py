"""Atomic persistence of generated images and versioned manifests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from PIL import Image

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import (
    FieldIssue,
    GenerationNotFoundError,
    GenerationRequestInvalidError,
    ManifestNotFoundError,
    ManifestSchemaUnsupportedError,
    OutputPersistenceError,
)
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.core.version import (
    API_MAJOR_VERSION,
    APPLICATION_NAME,
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
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest, GenerationResult
from unity_ai_assets.domain.generation_manifest import (
    GenerationManifest,
    ManifestApplicationInfo,
    ManifestGenerationInfo,
    ManifestModelInfo,
    ManifestOutputInfo,
    ManifestProcessingInfo,
    ManifestProfileInfo,
    ManifestRequestInfo,
    ManifestRuntimeInfo,
    ManifestSchemaInfo,
    ManifestSourceImageInfo,
    parse_manifest_payload,
)
from unity_ai_assets.processing.pipeline import ProcessingResult

logger = get_logger(__name__)

_OUTPUT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True, slots=True)
class GenerationArtifacts:
    """Resolved files for a single generation directory."""

    generation_id: str
    directory: Path
    image_path: Path
    metadata_path: Path


def validate_generation_id(generation_id: str) -> str:
    """Accept only UUID generation identifiers (rejects path traversal)."""
    raw = generation_id.strip()
    if not raw:
        raise GenerationRequestInvalidError(
            "generation_id must not be empty",
            field_issues={
                "generation_id": [
                    FieldIssue(
                        code=FieldIssueCode.FIELD_REQUIRED,
                        message="generation_id is required.",
                    )
                ]
            },
        )
    if "/" in raw or "\\" in raw or ".." in raw:
        raise GenerationRequestInvalidError(
            "generation_id must not contain path segments",
            field_issues={
                "generation_id": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_INVALID,
                        message="generation_id must not contain path segments.",
                        actual=raw,
                    )
                ]
            },
        )
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise GenerationRequestInvalidError(
            "generation_id must be a valid UUID",
            field_issues={
                "generation_id": [
                    FieldIssue(
                        code=FieldIssueCode.FORMAT_INVALID,
                        message="generation_id must be a valid UUID.",
                        actual=raw,
                    )
                ]
            },
        ) from exc


def sanitize_output_name(raw: str, *, max_length: int = 100) -> str:
    """Validate and normalize a user-supplied output basename (no path segments)."""
    name = raw.strip()
    if not name:
        raise GenerationRequestInvalidError(
            "output_name must not be empty",
            field_issues={
                "output_name": [
                    FieldIssue(
                        code=FieldIssueCode.FIELD_REQUIRED,
                        message="Output name is required.",
                    )
                ]
            },
        )
    if "/" in name or "\\" in name or ".." in name:
        raise GenerationRequestInvalidError(
            "output_name must not contain path separators or '..'",
            field_issues={
                "output_name": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_INVALID,
                        message="Output name must not contain path separators or '..'.",
                        actual=name,
                    )
                ]
            },
        )
    if len(name) > max_length:
        raise GenerationRequestInvalidError(
            "output_name exceeds maximum length",
            field_issues={
                "output_name": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_TOO_LONG,
                        message=f"Output name must be at most {max_length} characters.",
                        actual=len(name),
                        maximum=max_length,
                    )
                ]
            },
        )
    if not _OUTPUT_NAME_PATTERN.fullmatch(name):
        raise GenerationRequestInvalidError(
            "output_name has invalid format",
            field_issues={
                "output_name": [
                    FieldIssue(
                        code=FieldIssueCode.FORMAT_INVALID,
                        message=(
                            "Output name must start with an alphanumeric character and "
                            "contain only letters, digits, underscores, or hyphens."
                        ),
                        actual=name,
                    )
                ]
            },
        )
    return name


def sha256_file(path: Path) -> str:
    """Compute lowercase hex SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OutputService:
    """Writes generation outputs under a unique directory per generation ID."""

    def __init__(
        self,
        output_directory: Path,
        *,
        app_version: str,
        model_family: str = "unknown",
        default_scheduler: str = "pndm",
        max_output_name_length: int = 100,
    ) -> None:
        self._output_directory = output_directory
        self._app_version = app_version
        self._model_family = model_family
        self._default_scheduler = default_scheduler
        self._max_output_name_length = max_output_name_length

    @property
    def output_directory(self) -> Path:
        return self._output_directory

    def resolve_artifacts(self, generation_id: str) -> GenerationArtifacts:
        """Resolve final PNG + JSON for a generation ID without accepting filesystem paths."""
        safe_id = validate_generation_id(generation_id)
        root = self._output_directory.resolve()
        generation_dir = (self._output_directory / safe_id).resolve()

        if not str(generation_dir).startswith(str(root)):
            raise GenerationRequestInvalidError(
                "generation_id resolves outside the output directory",
                field_issues={
                    "generation_id": [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_INVALID,
                            message="generation_id resolves outside the output directory.",
                        )
                    ]
                },
            )
        if not generation_dir.is_dir():
            raise GenerationNotFoundError(f"No generation found for id '{safe_id}'")

        metadata_path = self._find_metadata_path(generation_dir)
        if metadata_path is None:
            raise ManifestNotFoundError(
                f"Generation '{safe_id}' does not contain a manifest or legacy metadata file"
            )

        image_path = self._resolve_final_image(generation_dir, metadata_path)
        metadata_resolved = metadata_path.resolve()
        if not str(image_path).startswith(str(generation_dir)) or not str(
            metadata_resolved
        ).startswith(str(generation_dir)):
            raise GenerationNotFoundError(
                f"Generation '{safe_id}' contains files outside its directory"
            )
        return GenerationArtifacts(
            generation_id=safe_id,
            directory=generation_dir,
            image_path=image_path,
            metadata_path=metadata_resolved,
        )

    def _resolve_final_image(self, generation_dir: Path, metadata_path: Path) -> Path:
        """Prefer the final processed image identified by the manifest."""
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                processing = payload.get("processing")
                if isinstance(processing, dict):
                    final_rel = processing.get("final_relative_path")
                    if isinstance(final_rel, str) and final_rel:
                        candidate = (generation_dir / final_rel).resolve()
                        if candidate.is_file() and str(candidate).startswith(str(generation_dir)):
                            return candidate
                outputs = payload.get("outputs")
                if isinstance(outputs, list):
                    for item in outputs:
                        if (
                            isinstance(item, dict)
                            and item.get("kind") == OutputKind.IMAGE.value
                            and isinstance(item.get("relative_path"), str)
                        ):
                            candidate = (generation_dir / str(item["relative_path"])).resolve()
                            if candidate.is_file() and str(candidate).startswith(
                                str(generation_dir)
                            ):
                                return candidate
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

        png_files = sorted(
            p
            for p in generation_dir.glob("*.png")
            if p.is_file() and not p.name.endswith(".original.png")
        )
        if len(png_files) == 1:
            return png_files[0].resolve()
        if not png_files:
            raise GenerationNotFoundError(
                f"Generation '{generation_dir.name}' does not contain a final image file"
            )
        # Prefer the shortest non-original name as a last resort.
        return min(png_files, key=lambda p: len(p.name)).resolve()

    def load_manifest(self, generation_id: str) -> GenerationManifest:
        """Load and parse the generation manifest (with legacy compatibility)."""
        artifacts = self.resolve_artifacts(generation_id)
        try:
            payload = json.loads(artifacts.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestNotFoundError(
                f"Could not read manifest for generation '{generation_id}'."
            ) from exc
        if not isinstance(payload, dict):
            raise ManifestSchemaUnsupportedError("Manifest root must be a JSON object.")
        try:
            return parse_manifest_payload(payload)
        except ManifestSchemaUnsupportedError:
            raise
        except ValueError as exc:
            raise ManifestSchemaUnsupportedError(str(exc)) from exc

    @staticmethod
    def _find_metadata_path(generation_dir: Path) -> Path | None:
        manifest = generation_dir / MANIFEST_FILENAME
        if manifest.is_file():
            return manifest
        json_files = sorted(p for p in generation_dir.glob("*.json") if p.is_file())
        if len(json_files) == 1:
            return json_files[0]
        return None

    def persist(
        self,
        request: GenerationRequest,
        generated: GeneratedImage,
        *,
        processing: ProcessingResult | None = None,
    ) -> GenerationResult:
        """Save PNG + versioned manifest; never overwrite an existing generation directory."""
        safe_name = sanitize_output_name(
            request.output_name,
            max_length=self._max_output_name_length,
        )
        generation_dir = (self._output_directory / request.generation_id).resolve()
        root = self._output_directory.resolve()

        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OutputPersistenceError(
                "Could not create the configured output directory."
            ) from exc

        if not str(generation_dir).startswith(str(root)):
            raise OutputPersistenceError("Resolved generation path escapes the output directory.")

        try:
            generation_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError as exc:
            raise OutputPersistenceError(
                f"Generation directory already exists for id '{request.generation_id}'."
            ) from exc
        except OSError as exc:
            raise OutputPersistenceError("Could not create generation output directory.") from exc

        image_filename = f"{safe_name}.png"
        image_path = generation_dir / image_filename
        manifest_path = generation_dir / MANIFEST_FILENAME
        original_filename: str | None = None
        original_path: Path | None = None

        created_at = datetime.now(UTC)
        try:
            if (
                processing is not None
                and processing.original_image is not None
                and (
                    processing.background_removal_applied
                    or processing.seam_correction_applied
                    or processing.palette_reduction_applied
                )
            ):
                original_filename = f"{safe_name}.original.png"
                original_path = generation_dir / original_filename
                self._write_pil_atomic(processing.original_image, original_path)

            self._write_image_atomic(generated, image_path)
            byte_size = image_path.stat().st_size
            digest = sha256_file(image_path)
            completed_at = datetime.now(UTC)

            outputs: list[ManifestOutputInfo] = [
                ManifestOutputInfo(
                    kind=OutputKind.IMAGE.value,
                    format=OutputFormat.PNG.value,
                    relative_path=image_filename,
                    width=generated.width,
                    height=generated.height,
                    sha256=digest,
                    byte_size=byte_size,
                )
            ]
            if (
                original_path is not None
                and original_filename is not None
                and processing is not None
            ):
                original_image = processing.original_image
                assert original_image is not None
                outputs.append(
                    ManifestOutputInfo(
                        kind=OutputKind.ORIGINAL_IMAGE.value,
                        format=OutputFormat.PNG.value,
                        relative_path=original_filename,
                        width=original_image.width,
                        height=original_image.height,
                        sha256=sha256_file(original_path),
                        byte_size=original_path.stat().st_size,
                    )
                )

            processing_info: ManifestProcessingInfo | None = None
            if processing is not None and (
                processing.background_removal_applied
                or processing.alpha_cleanup_applied
                or processing.seam_correction_applied
                or processing.palette_reduction_applied
                or processing.tileable
                or request.asset_type in {AssetType.SPRITE.value, AssetType.ICON.value}
            ):
                processing_info = ManifestProcessingInfo(
                    transparency_strategy=processing.transparency_strategy,
                    background_removal_applied=processing.background_removal_applied,
                    background_removal_implementation=processing.background_removal_implementation,
                    alpha_cleanup_applied=processing.alpha_cleanup_applied,
                    alpha_threshold=processing.alpha_threshold,
                    alpha_feather=processing.alpha_feather,
                    remove_near_transparent=processing.remove_near_transparent,
                    zero_rgb_when_transparent=processing.zero_rgb_when_transparent,
                    pixels_per_unit=request.pixels_per_unit,
                    pivot_mode=request.pivot_mode,
                    custom_pivot_x=request.custom_pivot_x,
                    custom_pivot_y=request.custom_pivot_y,
                    atlas_hint=request.atlas_hint,
                    original_relative_path=original_filename,
                    final_relative_path=image_filename,
                    tileable=processing.tileable,
                    seam_correction_applied=processing.seam_correction_applied,
                    palette_reduction_applied=processing.palette_reduction_applied,
                    seam_blend_width=processing.seam_blend_width,
                    palette_color_count=processing.palette_color_count,
                    seam_score_before=processing.seam_score_before,
                    seam_score_after=processing.seam_score_after,
                    horizontal_seam_score=processing.horizontal_seam_score,
                    vertical_seam_score=processing.vertical_seam_score,
                    horizontal_wrap_discontinuity=processing.horizontal_wrap_discontinuity,
                    vertical_wrap_discontinuity=processing.vertical_wrap_discontinuity,
                    seam_inpaint_implementation=processing.seam_inpaint_implementation,
                )

            manifest = GenerationManifest(
                schema=ManifestSchemaInfo(
                    name=GENERATION_MANIFEST_SCHEMA_NAME,
                    version=GENERATION_MANIFEST_SCHEMA_VERSION,
                ),
                generation=ManifestGenerationInfo(
                    id=request.generation_id,
                    operation=request.operation or OperationType.TEXT_TO_IMAGE.value,
                    asset_type=request.asset_type or AssetType.TEXTURE.value,
                    status=GenerationStatus.COMPLETED.value,
                    created_at_utc=created_at,
                    completed_at_utc=completed_at,
                    elapsed_seconds=generated.elapsed_seconds,
                ),
                application=ManifestApplicationInfo(
                    name=APPLICATION_NAME,
                    version=self._app_version,
                    api_major=API_MAJOR_VERSION,
                ),
                model=ManifestModelInfo(
                    id=generated.model_id,
                    revision=generated.model_revision,
                    family=self._model_family,
                ),
                runtime=ManifestRuntimeInfo(
                    device=generated.device,
                    precision=generated.torch_dtype,
                    scheduler=self._default_scheduler,
                ),
                request=ManifestRequestInfo(
                    prompt=request.prompt,
                    negative_prompt=request.negative_prompt,
                    width=generated.width,
                    height=generated.height,
                    steps=request.steps,
                    guidance_scale=request.guidance_scale,
                    seed=generated.seed,
                    output_name=safe_name,
                    transparency_strategy=request.transparency_strategy,
                    alpha_threshold=request.alpha_threshold,
                    alpha_feather=request.alpha_feather,
                    remove_near_transparent=request.remove_near_transparent,
                    zero_rgb_when_transparent=request.zero_rgb_when_transparent,
                    pixels_per_unit=request.pixels_per_unit,
                    pivot_mode=request.pivot_mode,
                    custom_pivot_x=request.custom_pivot_x,
                    custom_pivot_y=request.custom_pivot_y,
                    atlas_hint=request.atlas_hint,
                    tileable=request.tileable,
                    apply_seam_correction=request.apply_seam_correction,
                    seam_blend_width=request.seam_blend_width,
                    palette_reduction_enabled=request.palette_reduction_enabled,
                    palette_color_count=request.palette_color_count,
                    denoising_strength=request.denoising_strength,
                    source_image=(
                        None
                        if request.source_image_meta is None
                        else ManifestSourceImageInfo(
                            format=request.source_image_meta.format,
                            media_type=request.source_image_meta.media_type,
                            width=request.source_image_meta.original_width,
                            height=request.source_image_meta.original_height,
                            byte_size=request.source_image_meta.byte_size,
                            sha256=request.source_image_meta.sha256,
                        )
                    ),
                    mask_image=(
                        None
                        if request.mask_image_meta is None
                        else ManifestSourceImageInfo(
                            format=request.mask_image_meta.format,
                            media_type=request.mask_image_meta.media_type,
                            width=request.mask_image_meta.original_width,
                            height=request.mask_image_meta.original_height,
                            byte_size=request.mask_image_meta.byte_size,
                            sha256=request.mask_image_meta.sha256,
                        )
                    ),
                    mask_convention=request.mask_convention,
                ),
                profile=ManifestProfileInfo(
                    generation_profile_id=request.generation_profile_id,
                    generation_profile_revision=request.generation_profile_revision,
                    profile_origin=request.profile_origin or "none",
                    prompt_template_id=request.prompt_template_id,
                    prompt_template_revision=request.prompt_template_revision,
                    negative_prompt_profile_id=request.negative_prompt_profile_id,
                    negative_prompt_profile_revision=request.negative_prompt_profile_revision,
                    unity_import_profile_id=request.unity_import_profile_id,
                ),
                outputs=outputs,
                processing=processing_info,
            )
            self._write_json_atomic(manifest.to_dict(), manifest_path)
        except OSError as exc:
            raise OutputPersistenceError("Failed while writing generation output files.") from exc

        image_url = f"/api/v1/generations/{request.generation_id}/image"
        manifest_url = f"/api/v1/generations/{request.generation_id}/manifest"
        display_image = self._display_path(image_path)
        display_manifest = self._display_path(manifest_path)

        logger.info(
            "Persisted generation_id=%s image=%s manifest=%s sha256=%s bytes=%s",
            request.generation_id,
            display_image,
            display_manifest,
            digest,
            byte_size,
        )
        return GenerationResult(
            generation_id=request.generation_id,
            status=GenerationStatus.COMPLETED.value,
            operation=request.operation or OperationType.TEXT_TO_IMAGE.value,
            asset_type=request.asset_type or AssetType.TEXTURE.value,
            image_path=display_image,
            metadata_path=display_manifest,
            image_url=image_url,
            manifest_url=manifest_url,
            seed=generated.seed,
            width=generated.width,
            height=generated.height,
            elapsed_seconds=generated.elapsed_seconds,
            manifest_schema_version=GENERATION_MANIFEST_SCHEMA_VERSION,
            image_sha256=digest,
            image_byte_size=byte_size,
        )

    @staticmethod
    def _display_path(path: Path) -> str:
        """Return a cwd-relative path when possible (deprecated public use)."""
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(Path.cwd().resolve())).replace("\\", "/")
        except ValueError:
            return str(resolved).replace("\\", "/")

    @staticmethod
    def _write_pil_atomic(image: Image.Image, destination: Path) -> None:
        directory = destination.parent
        fd, temp_name = tempfile.mkstemp(suffix=".png", dir=directory)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            image.save(temp_path, format="PNG")
            os.replace(temp_path, destination)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    @classmethod
    def _write_image_atomic(cls, generated: GeneratedImage, destination: Path) -> None:
        cls._write_pil_atomic(generated.image, destination)

    @staticmethod
    def _write_json_atomic(payload: dict[str, object], destination: Path) -> None:
        directory = destination.parent
        fd, temp_name = tempfile.mkstemp(suffix=".json", dir=directory)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            temp_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temp_path, destination)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
