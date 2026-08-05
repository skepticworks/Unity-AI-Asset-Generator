"""Atomic persistence of generated images and metadata."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from unity_ai_assets.core.errors import InvalidGenerationParametersError, OutputPersistenceError
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.domain.generation import (
    GeneratedImage,
    GenerationMetadata,
    GenerationRequest,
    GenerationResult,
)

logger = get_logger(__name__)

_OUTPUT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def sanitize_output_name(raw: str) -> str:
    """Validate and normalize a user-supplied output basename (no path segments)."""
    name = raw.strip()
    if not name:
        raise InvalidGenerationParametersError("output_name must not be empty")
    if "/" in name or "\\" in name or ".." in name:
        raise InvalidGenerationParametersError(
            "output_name must not contain path separators or '..'"
        )
    if not _OUTPUT_NAME_PATTERN.fullmatch(name):
        raise InvalidGenerationParametersError(
            "output_name must start with an alphanumeric character and contain only "
            "letters, digits, underscores, or hyphens (max 64 characters)"
        )
    return name


class OutputService:
    """Writes generation outputs under a unique directory per generation ID."""

    def __init__(self, output_directory: Path, *, app_version: str) -> None:
        self._output_directory = output_directory
        self._app_version = app_version

    def persist(
        self,
        request: GenerationRequest,
        generated: GeneratedImage,
    ) -> GenerationResult:
        """Save PNG + JSON metadata; never overwrite an existing generation directory."""
        safe_name = sanitize_output_name(request.output_name)
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
        metadata_filename = f"{safe_name}.json"
        image_path = generation_dir / image_filename
        metadata_path = generation_dir / metadata_filename

        metadata = GenerationMetadata(
            generation_id=request.generation_id,
            created_at_utc=datetime.now(UTC),
            model_id=generated.model_id,
            model_revision=generated.model_revision,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            seed=generated.seed,
            width=generated.width,
            height=generated.height,
            steps=request.steps,
            guidance_scale=request.guidance_scale,
            device=generated.device,
            torch_dtype=generated.torch_dtype,
            app_version=self._app_version,
            elapsed_seconds=generated.elapsed_seconds,
            output_filename=image_filename,
        )

        try:
            self._write_image_atomic(generated, image_path)
            self._write_json_atomic(metadata.to_dict(), metadata_path)
        except OSError as exc:
            raise OutputPersistenceError("Failed while writing generation output files.") from exc

        display_image = self._display_path(image_path)
        display_metadata = self._display_path(metadata_path)

        logger.info(
            "Persisted generation_id=%s image=%s metadata=%s",
            request.generation_id,
            display_image,
            display_metadata,
        )
        return GenerationResult(
            generation_id=request.generation_id,
            status="completed",
            image_path=display_image,
            metadata_path=display_metadata,
            seed=generated.seed,
            width=generated.width,
            height=generated.height,
            elapsed_seconds=generated.elapsed_seconds,
        )

    @staticmethod
    def _display_path(path: Path) -> str:
        """Return a stable path string: cwd-relative when possible, else absolute."""
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
