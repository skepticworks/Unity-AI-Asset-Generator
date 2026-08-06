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
    ManifestRequestInfo,
    ManifestRuntimeInfo,
    ManifestSchemaInfo,
    parse_manifest_payload,
)

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
        """Resolve PNG + JSON for a generation ID without accepting filesystem paths."""
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

        png_files = sorted(generation_dir.glob("*.png"))
        if len(png_files) != 1:
            raise GenerationNotFoundError(
                f"Generation '{safe_id}' does not contain exactly one image file"
            )

        metadata_path = self._find_metadata_path(generation_dir)
        if metadata_path is None:
            raise ManifestNotFoundError(
                f"Generation '{safe_id}' does not contain a manifest or legacy metadata file"
            )

        image_path = png_files[0].resolve()
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

        created_at = datetime.now(UTC)
        try:
            self._write_image_atomic(generated, image_path)
            byte_size = image_path.stat().st_size
            digest = sha256_file(image_path)
            completed_at = datetime.now(UTC)

            manifest = GenerationManifest(
                schema=ManifestSchemaInfo(
                    name=GENERATION_MANIFEST_SCHEMA_NAME,
                    version=GENERATION_MANIFEST_SCHEMA_VERSION,
                ),
                generation=ManifestGenerationInfo(
                    id=request.generation_id,
                    operation=OperationType.TEXT_TO_IMAGE.value,
                    asset_type=AssetType.TEXTURE.value,
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
                ),
                outputs=[
                    ManifestOutputInfo(
                        kind=OutputKind.IMAGE.value,
                        format=OutputFormat.PNG.value,
                        relative_path=image_filename,
                        width=generated.width,
                        height=generated.height,
                        sha256=digest,
                        byte_size=byte_size,
                    )
                ],
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
            operation=OperationType.TEXT_TO_IMAGE.value,
            asset_type=AssetType.TEXTURE.value,
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
    def _write_image_atomic(generated: GeneratedImage, destination: Path) -> None:
        directory = destination.parent
        fd, temp_name = tempfile.mkstemp(suffix=".png", dir=directory)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            generated.image.save(temp_path, format="PNG")
            os.replace(temp_path, destination)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

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
