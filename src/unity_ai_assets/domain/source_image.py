"""Validation and decoding of img2img source (init) images.

The source image is the generation starting latent / init image. It is not a
reference-conditioning input (IP-Adapter, style/identity references, etc.).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
from dataclasses import dataclass
from typing import NoReturn

from PIL import Image, UnidentifiedImageError

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import FieldIssue, GenerationRequestInvalidError
from unity_ai_assets.domain.generation import SourceImageMetadata
from unity_ai_assets.domain.generation_policy import GenerationPolicy

SUPPORTED_SOURCE_IMAGE_FORMATS: tuple[str, ...] = ("png", "jpeg", "webp")
SOURCE_IMAGE_MEDIA_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
_MEDIA_TYPE_ALIASES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/webp": "webp",
    "png": "png",
    "jpeg": "jpeg",
    "jpg": "jpeg",
    "webp": "webp",
}

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_WEBP_RIFF = b"RIFF"
_WEBP_WEBP = b"WEBP"


@dataclass(frozen=True, slots=True)
class ValidatedSourceImage:
    """Decoded, policy-validated img2img init image plus original metadata."""

    image: Image.Image
    metadata: SourceImageMetadata


def _detect_format_from_magic(payload: bytes) -> str | None:
    if payload.startswith(_PNG_MAGIC):
        return "png"
    if payload.startswith(_JPEG_MAGIC):
        return "jpeg"
    if len(payload) >= 12 and payload.startswith(_WEBP_RIFF) and payload[8:12] == _WEBP_WEBP:
        return "webp"
    return None


def _normalize_media_type(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    if not text:
        return None
    return _MEDIA_TYPE_ALIASES.get(text)


def _normalize_pillow_format(raw_format: str | None) -> str | None:
    if not raw_format:
        return None
    name = raw_format.strip().lower()
    if name == "jpg":
        return "jpeg"
    if name in SUPPORTED_SOURCE_IMAGE_FORMATS:
        return name
    return None


def _invalid(
    field: str,
    code: FieldIssueCode,
    message: str,
    *,
    actual: object = None,
    minimum: object = None,
    maximum: object = None,
    expected_multiple: int | None = None,
) -> NoReturn:
    raise GenerationRequestInvalidError(
        message,
        field_issues={
            field: [
                FieldIssue(
                    code=code,
                    message=message,
                    actual=actual,
                    minimum=minimum,
                    maximum=maximum,
                    expected_multiple=expected_multiple,
                )
            ]
        },
    )


def decode_source_image_base64(content_base64: str) -> bytes:
    """Decode base64 source-image bytes or raise a field-level validation error."""
    if content_base64 is None or not str(content_base64).strip():
        _invalid(
            "source_image",
            FieldIssueCode.FIELD_REQUIRED,
            "source_image.content_base64 is required for image_to_image.",
        )
    text = str(content_base64).strip()
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        _invalid(
            "source_image.content_base64",
            FieldIssueCode.FORMAT_INVALID,
            "source_image.content_base64 must be valid base64.",
        )


def validate_source_image(
    *,
    raw_bytes: bytes,
    policy: GenerationPolicy,
    media_type: str | None = None,
) -> ValidatedSourceImage:
    """Validate uploaded bytes and return an RGB init image plus metadata.

    Rejects unsupported formats, oversize payloads, out-of-policy dimensions,
    and corrupt/unreadable images. Does not treat the image as reference
    conditioning.
    """
    if not raw_bytes:
        _invalid(
            "source_image",
            FieldIssueCode.FIELD_REQUIRED,
            "source_image must not be empty.",
        )

    byte_size = len(raw_bytes)
    if byte_size > policy.maximum_source_image_bytes:
        _invalid(
            "source_image",
            FieldIssueCode.VALUE_ABOVE_MAXIMUM,
            (
                "Source image exceeds the maximum upload size of "
                f"{policy.maximum_source_image_bytes} bytes."
            ),
            actual=byte_size,
            maximum=policy.maximum_source_image_bytes,
        )

    declared_format = _normalize_media_type(media_type)
    magic_format = _detect_format_from_magic(raw_bytes)
    if declared_format is not None and magic_format is not None and declared_format != magic_format:
        _invalid(
            "source_image.media_type",
            FieldIssueCode.FORMAT_INVALID,
            (
                f"Declared media type '{media_type}' does not match the encoded "
                f"image format '{magic_format}'."
            ),
            actual=media_type,
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            probe.verify()
        loaded = Image.open(io.BytesIO(raw_bytes))
        loaded.load()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise GenerationRequestInvalidError(
            "The source image could not be decoded (corrupt or unsupported).",
            field_issues={
                "source_image": [
                    FieldIssue(
                        code=FieldIssueCode.FORMAT_INVALID,
                        message=(
                            "The source image could not be decoded. "
                            "Upload a valid PNG, JPEG, or WebP image."
                        ),
                    )
                ]
            },
        ) from exc

    pillow_format = _normalize_pillow_format(loaded.format)
    detected = declared_format or magic_format or pillow_format
    if detected is None or detected not in policy.supported_source_image_formats:
        actual = detected or pillow_format or (loaded.format or "unknown")
        loaded.close()
        _invalid(
            "source_image",
            FieldIssueCode.FORMAT_INVALID,
            (
                "Unsupported source image format "
                f"'{actual}'. Supported formats: "
                + ", ".join(policy.supported_source_image_formats)
                + "."
            ),
            actual=actual,
        )

    original_width, original_height = loaded.size
    try:
        policy.validate_dimensions(original_width, original_height)
    except GenerationRequestInvalidError as exc:
        loaded.close()
        remapped: dict[str, list[FieldIssue]] = {}
        for field, issues in exc.field_issues.items():
            remapped[f"source_image.{field}"] = [
                FieldIssue(
                    code=issue.code,
                    message=f"Source image {issue.message[0].lower() + issue.message[1:]}",
                    actual=issue.actual,
                    minimum=issue.minimum,
                    maximum=issue.maximum,
                    expected_multiple=issue.expected_multiple,
                )
                for issue in issues
            ]
        raise GenerationRequestInvalidError(
            "Source image dimensions are invalid.",
            field_issues=remapped,
        ) from exc

    rgb = loaded.convert("RGB")
    if rgb is not loaded:
        loaded.close()

    digest = hashlib.sha256(raw_bytes).hexdigest()
    metadata = SourceImageMetadata(
        format=detected,
        media_type=SOURCE_IMAGE_MEDIA_TYPES[detected],
        original_width=original_width,
        original_height=original_height,
        byte_size=byte_size,
        sha256=digest,
    )
    return ValidatedSourceImage(image=rgb, metadata=metadata)


def prepare_init_image(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return an RGB init image at the generation size using deterministic LANCZOS."""
    rgb = image if image.mode == "RGB" else image.convert("RGB")
    if rgb.size == (width, height):
        return rgb
    return rgb.resize((width, height), Image.Resampling.LANCZOS)
