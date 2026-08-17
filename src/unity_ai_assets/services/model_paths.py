"""Filesystem helpers for managed model storage and path safety."""

from __future__ import annotations

import contextlib
import re
import shutil
from pathlib import Path

from unity_ai_assets.core.errors import ModelOutsideStorageBoundaryError, ModelStorageInvalidError

_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
MAX_MODEL_ID_LENGTH = 120


def slugify_model_id(identifier: str) -> str:
    """Turn a Hugging Face repo id or folder name into a filesystem-safe slug."""
    raw = identifier.strip().replace("\\", "/").strip("/")
    if not raw:
        raise ModelStorageInvalidError("Model identifier must not be empty.")
    if ".." in raw.split("/"):
        raise ModelOutsideStorageBoundaryError(
            "Model identifier must not contain parent-directory segments."
        )
    slug = _UNSAFE_ID_CHARS.sub("__", raw.replace("/", "__"))
    slug = slug.strip("._-") or "model"
    if len(slug) > MAX_MODEL_ID_LENGTH:
        slug = slug[:MAX_MODEL_ID_LENGTH].rstrip("._-") or "model"
    return slug


def resolve_existing_path(path: Path) -> Path:
    """Resolve a path, including the last existing parent when the target is new."""
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


def is_within_directory(path: Path, root: Path) -> bool:
    """Return True when ``path`` is the same as or a descendant of ``root``."""
    try:
        resolved = resolve_existing_path(path)
        root_resolved = resolve_existing_path(root)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        return False
    return True


def assert_within_storage(path: Path, roots: list[Path], *, allow_root: bool = False) -> Path:
    """Reject paths that escape every managed storage root."""
    resolved = resolve_existing_path(path)
    for root in roots:
        root_resolved = resolve_existing_path(root)
        if not is_within_directory(resolved, root_resolved):
            continue
        if not allow_root and resolved == root_resolved:
            raise ModelOutsideStorageBoundaryError(
                "Refusing to operate on the model-storage root itself.",
                details={"path": str(resolved), "storage": str(root_resolved)},
            )
        return resolved
    raise ModelOutsideStorageBoundaryError(
        "The requested path is outside the managed model-storage boundary.",
        details={"path": str(resolved)},
    )


def ensure_storage_directory(path: Path, *, create: bool = True) -> tuple[Path, bool]:
    """Create or validate a storage directory. Returns (resolved, created)."""
    resolved = resolve_existing_path(path)
    created = False
    if resolved.exists() and not resolved.is_dir():
        raise ModelStorageInvalidError(
            "Model storage path exists but is not a directory.",
            details={"path": str(resolved)},
        )
    if not resolved.exists():
        if not create:
            raise ModelStorageInvalidError(
                "Model storage directory does not exist.",
                details={"path": str(resolved)},
            )
        try:
            resolved.mkdir(parents=True, exist_ok=True)
            created = True
        except OSError as exc:
            raise ModelStorageInvalidError(
                "Could not create the model storage directory.",
                details={"path": str(resolved), "reason": type(exc).__name__},
            ) from exc
    if not _is_accessible(resolved):
        raise ModelStorageInvalidError(
            "Model storage directory is not accessible.",
            details={"path": str(resolved)},
        )
    return resolved, created


def inspect_storage_directory(path: Path) -> tuple[bool, bool, bool, str | None]:
    """Return (exists, accessible, writable, issue) without raising."""
    resolved = resolve_existing_path(path)
    if not resolved.exists():
        return False, False, False, "Directory does not exist."
    if not resolved.is_dir():
        return True, False, False, "Path exists but is not a directory."
    if not _is_accessible(resolved):
        return True, False, False, "Directory is not readable."
    writable = _is_writable(resolved)
    issue = None if writable else "Directory is not writable."
    return True, True, writable, issue


def volume_usage(path: Path) -> tuple[int | None, int | None]:
    """Return (free_bytes, total_bytes) for the volume containing ``path``."""
    probe = resolve_existing_path(path)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        usage = shutil.disk_usage(probe)
    except OSError:
        return None, None
    return int(usage.free), int(usage.total)


def directory_size_bytes(path: Path) -> int:
    """Walk ``path`` and sum file sizes. Caller should cache the result."""
    total = 0
    if not path.exists():
        return 0
    for child in path.rglob("*"):
        if not child.is_file():
            continue
        try:
            total += child.stat().st_size
        except OSError:
            continue
    return total


def _is_accessible(path: Path) -> bool:
    try:
        next(path.iterdir(), None)
        return True
    except OSError:
        return False


def _is_writable(path: Path) -> bool:
    probe = path / ".write-test.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False
    finally:
        if probe.exists():
            with contextlib.suppress(OSError):
                probe.unlink()
