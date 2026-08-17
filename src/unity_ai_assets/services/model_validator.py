"""Structural, type, hash, and load-compatibility checks for managed models."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from unity_ai_assets.domain.enums import ModelValidationState
from unity_ai_assets.domain.installed_models import (
    COMPATIBILITY_FILENAME,
    METADATA_FILENAME,
    ModelFileHash,
    ModelValidationIssue,
    ModelValidationReport,
)
from unity_ai_assets.domain.model_compatibility import (
    DEFAULT_REQUIRED_COMPONENTS,
    KNOWN_PIPELINE_CLASSES,
    family_from_pipeline_class,
)

HASHABLE_SUFFIXES = {
    ".safetensors",
    ".bin",
    ".json",
    ".txt",
    ".model",
    ".onnx",
    ".pt",
    ".ckpt",
}
SKIP_NAMES = {
    METADATA_FILENAME,
    COMPATIBILITY_FILENAME,
    ".git",
    "__pycache__",
}
SKIP_DIR_NAMES = {".git", "__pycache__", ".staging"}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_model_index(directory: Path) -> dict[str, object] | None:
    index_path = directory / "model_index.json"
    if not index_path.is_file():
        return None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def pipeline_class_from_index(index: dict[str, object] | None) -> str | None:
    if not index:
        return None
    value = index.get("_class_name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def required_components_from_index(index: dict[str, object] | None) -> tuple[str, ...]:
    if not index:
        return DEFAULT_REQUIRED_COMPONENTS
    names: list[str] = []
    for key, value in index.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list) and value:
            names.append(str(key))
    return tuple(names) if names else DEFAULT_REQUIRED_COMPONENTS


def iter_model_files(directory: Path) -> list[Path]:
    files: list[Path] = []
    for child in sorted(directory.rglob("*")):
        if not child.is_file():
            continue
        relative_parts = child.relative_to(directory).parts
        hidden = any(
            part.startswith(".") or part in SKIP_DIR_NAMES or part in SKIP_NAMES
            for part in relative_parts
        )
        if hidden:
            continue
        if child.name.startswith(".") or child.name in SKIP_NAMES:
            continue
        if child.suffix.lower() not in HASHABLE_SUFFIXES and child.name != "model_index.json":
            continue
        files.append(child)
    return files


def compute_file_hashes(directory: Path) -> tuple[ModelFileHash, ...]:
    hashes: list[ModelFileHash] = []
    for path in iter_model_files(directory):
        relative = path.relative_to(directory).as_posix()
        try:
            digest = sha256_file(path)
            size = path.stat().st_size
        except OSError:
            continue
        hashes.append(ModelFileHash(path=relative, sha256=digest, byte_size=size))
    return tuple(hashes)


def validate_model_directory(
    directory: Path,
    *,
    expected_hashes: tuple[ModelFileHash, ...] | None = None,
    required_components: tuple[str, ...] | None = None,
) -> ModelValidationReport:
    """Validate structure, type, and hashes. Does not load GPU weights."""
    issues: list[ModelValidationIssue] = []
    if not directory.exists() or not directory.is_dir():
        issues.append(
            ModelValidationIssue(
                code="DIRECTORY_MISSING",
                message="Model directory is missing.",
                path=str(directory),
            )
        )
        return ModelValidationReport(
            state=ModelValidationState.INVALID,
            checked_at=utc_now_iso(),
            issues=tuple(issues),
        )

    index = read_model_index(directory)
    if index is None:
        issues.append(
            ModelValidationIssue(
                code="MODEL_INDEX_MISSING",
                message="model_index.json is missing or is not valid JSON.",
                path="model_index.json",
            )
        )
    pipeline_class = pipeline_class_from_index(index)
    if index is not None and not pipeline_class:
        issues.append(
            ModelValidationIssue(
                code="PIPELINE_CLASS_MISSING",
                message="model_index.json does not declare _class_name.",
                path="model_index.json",
            )
        )
    elif pipeline_class and pipeline_class not in KNOWN_PIPELINE_CLASSES:
        # Unknown class is allowed but recorded; load compatibility is "basic".
        issues.append(
            ModelValidationIssue(
                code="PIPELINE_CLASS_UNKNOWN",
                message=(
                    f"Pipeline class '{pipeline_class}' is not a known Diffusers "
                    "text-to-image family; the model is stored but capability "
                    "checks will treat the family as unknown."
                ),
                path="model_index.json",
            )
        )

    components = required_components or required_components_from_index(index)
    for component in components:
        component_dir = directory / component
        if not component_dir.exists():
            issues.append(
                ModelValidationIssue(
                    code="COMPONENT_MISSING",
                    message=f"Required component '{component}' is missing.",
                    path=component,
                )
            )
            continue
        has_payload = any(component_dir.rglob("*.json")) or any(
            child.is_file() for child in component_dir.rglob("*")
        )
        if not has_payload:
            issues.append(
                ModelValidationIssue(
                    code="COMPONENT_EMPTY",
                    message=f"Required component '{component}' has no files.",
                    path=component,
                )
            )

    weight_files = [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in {".safetensors", ".bin", ".ckpt", ".pt"}
    ]
    if not weight_files:
        issues.append(
            ModelValidationIssue(
                code="WEIGHTS_MISSING",
                message="No model weight files (.safetensors/.bin) were found.",
            )
        )

    current_hashes = {item.path: item for item in compute_file_hashes(directory)}
    if expected_hashes is not None:
        expected_map = {item.path: item for item in expected_hashes}
        for relative, expected in expected_map.items():
            actual = current_hashes.get(relative)
            if actual is None:
                issues.append(
                    ModelValidationIssue(
                        code="FILE_MISSING",
                        message="A hashed model file is missing.",
                        path=relative,
                    )
                )
                continue
            if actual.byte_size != expected.byte_size:
                issues.append(
                    ModelValidationIssue(
                        code="FILE_SIZE_MISMATCH",
                        message=(
                            f"File size mismatch: expected {expected.byte_size}, "
                            f"got {actual.byte_size}."
                        ),
                        path=relative,
                    )
                )
            if actual.sha256.lower() != expected.sha256.lower():
                issues.append(
                    ModelValidationIssue(
                        code="HASH_MISMATCH",
                        message="SHA-256 does not match the persisted digest.",
                        path=relative,
                    )
                )
        for relative in current_hashes:
            if relative not in expected_map and relative != "model_index.json":
                # Extra files are informational, not a hard failure.
                continue

    blocking = [
        issue
        for issue in issues
        if issue.code
        not in {
            "PIPELINE_CLASS_UNKNOWN",
        }
    ]
    state = ModelValidationState.VALID if not blocking else ModelValidationState.INVALID
    return ModelValidationReport(
        state=state,
        checked_at=utc_now_iso(),
        issues=tuple(issues),
    )


def infer_family(directory: Path, fallback: str = "unknown") -> str:
    index = read_model_index(directory)
    family = family_from_pipeline_class(pipeline_class_from_index(index))
    return family if family != "unknown" else fallback
