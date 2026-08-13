"""Shared decoding helpers for uploaded PNG, JPEG, and WebP images."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
from dataclasses import dataclass
from typing import NoReturn

from PIL import Image, ImageOps, UnidentifiedImageError

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import FieldIssue, GenerationRequestInvalidError
from unity_ai_assets.domain.generation_policy import GenerationPolicy

SUPPORTED_UPLOAD_IMAGE_FORMATS: tuple[str, ...] = ("png", "jpeg", "webp")
UPLOAD_IMAGE_MEDIA_TYPES: dict[str, str] = {
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
class LoadedUpload:
    """Decoded upload plus original-file metadata (pixels are not persisted)."""

    image: Image.Image
    format: str
    media_type: str
    original_width: int
    original_height: int
    byte_size: int
    sha256: str


def detect_format_from_magic(payload: bytes) -> str | None:
    if payload.startswith(_PNG_MAGIC):
        return "png"
    if payload.startswith(_JPEG_MAGIC):
        return "jpeg"
    if len(payload) >= 12 and payload.startswith(_WEBP_RIFF) and payload[8:12] == _WEBP_WEBP:
        return "webp"
    return None


def normalize_media_type(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    if not text:
        return None
    return _MEDIA_TYPE_ALIASES.get(text)


def normalize_pillow_format(raw_format: str | None) -> str | None:
    if not raw_format:
        return None
    name = raw_format.strip().lower()
    if name == "jpg":
        return "jpeg"
    if name in SUPPORTED_UPLOAD_IMAGE_FORMATS:
        return name
    return None


def invalid_upload(
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


def decode_image_base64(content_base64: str, *, field: str) -> bytes:
    """Decode base64 image bytes or raise a field-level validation error."""
    if content_base64 is None or not str(content_base64).strip():
        invalid_upload(
            field,
            FieldIssueCode.FIELD_REQUIRED,
            f"{field}.content_base64 is required.",
        )
    text = str(content_base64).strip()
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        invalid_upload(
            f"{field}.content_base64",
            FieldIssueCode.FORMAT_INVALID,
            f"{field}.content_base64 must be valid base64.",
        )


def apply_exif_orientation(image: Image.Image) -> Image.Image:
    """Honor embedded EXIF orientation so source and mask stay aligned."""
    return ImageOps.exif_transpose(image) or image


def luminance_ignoring_alpha(image: Image.Image) -> Image.Image:
    """Return an L-mode image from color channels only.

    Alpha is discarded and never treated as mask or luminance. Transparent pixels
    therefore cannot flip white/black inpaint semantics.
    """
    if image.mode == "L":
        return image.copy()
    if image.mode == "1":
        return image.convert("L")
    if image.mode == "LA":
        return image.split()[0].copy()
    if image.mode == "RGBA":
        red, green, blue, _alpha = image.split()
        return Image.merge("RGB", (red, green, blue)).convert("L")
    if image.mode == "PA":
        rgba = image.convert("RGBA")
        red, green, blue, _alpha = rgba.split()
        return Image.merge("RGB", (red, green, blue)).convert("L")
    if image.mode == "P":
        # Convert via RGBA so palette transparency is not baked into luminance.
        rgba = image.convert("RGBA")
        red, green, blue, _alpha = rgba.split()
        return Image.merge("RGB", (red, green, blue)).convert("L")
    rgb = image.convert("RGB")
    return rgb.convert("L")


def rgb_ignoring_alpha(image: Image.Image) -> Image.Image:
    """Return RGB, compositing transparent pixels on black without using alpha as data.

    Pillow's ``convert("RGB")`` composites on black. That RGB conversion is the
    inpaint init image; it does not alter the separate mask.
    """
    if image.mode == "RGB":
        return image.copy()
    if image.mode in {"RGBA", "LA", "PA", "P"}:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (0, 0, 0))
        background.paste(rgba, mask=rgba.split()[3])
        return background
    return image.convert("RGB")


def load_uploaded_image(
    *,
    raw_bytes: bytes,
    policy: GenerationPolicy,
    media_type: str | None,
    field: str,
    maximum_bytes: int,
    supported_formats: tuple[str, ...],
    apply_exif: bool,
) -> LoadedUpload:
    """Validate uploaded bytes and return the loaded image plus file metadata."""
    if not raw_bytes:
        invalid_upload(field, FieldIssueCode.FIELD_REQUIRED, f"{field} must not be empty.")

    byte_size = len(raw_bytes)
    if byte_size > maximum_bytes:
        invalid_upload(
            field,
            FieldIssueCode.VALUE_ABOVE_MAXIMUM,
            f"{field.replace('_', ' ').capitalize()} exceeds the maximum upload size of "
            f"{maximum_bytes} bytes.",
            actual=byte_size,
            maximum=maximum_bytes,
        )

    declared_format = normalize_media_type(media_type)
    magic_format = detect_format_from_magic(raw_bytes)
    if declared_format is not None and magic_format is not None and declared_format != magic_format:
        invalid_upload(
            f"{field}.media_type",
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
            f"The {field.replace('_', ' ')} could not be decoded (corrupt or unsupported).",
            field_issues={
                field: [
                    FieldIssue(
                        code=FieldIssueCode.FORMAT_INVALID,
                        message=(
                            f"The {field.replace('_', ' ')} could not be decoded. "
                            "Upload a valid PNG, JPEG, or WebP image."
                        ),
                    )
                ]
            },
        ) from exc

    pillow_format = normalize_pillow_format(loaded.format)
    if apply_exif:
        oriented = apply_exif_orientation(loaded)
        if oriented is not loaded:
            loaded.close()
            loaded = oriented

    detected = declared_format or magic_format or pillow_format
    if detected is None or detected not in supported_formats:
        actual = detected or pillow_format or (loaded.format or "unknown")
        loaded.close()
        invalid_upload(
            field,
            FieldIssueCode.FORMAT_INVALID,
            (
                f"Unsupported {field.replace('_', ' ')} format '{actual}'. "
                "Supported formats: " + ", ".join(supported_formats) + "."
            ),
            actual=actual,
        )

    original_width, original_height = loaded.size
    try:
        policy.validate_dimensions(original_width, original_height)
    except GenerationRequestInvalidError as exc:
        loaded.close()
        remapped: dict[str, list[FieldIssue]] = {}
        label = field.replace("_", " ").capitalize()
        for issue_field, issues in exc.field_issues.items():
            remapped[f"{field}.{issue_field}"] = [
                FieldIssue(
                    code=issue.code,
                    message=f"{label} {issue.message[0].lower() + issue.message[1:]}",
                    actual=issue.actual,
                    minimum=issue.minimum,
                    maximum=issue.maximum,
                    expected_multiple=issue.expected_multiple,
                )
                for issue in issues
            ]
        raise GenerationRequestInvalidError(
            f"{label} dimensions are invalid.",
            field_issues=remapped,
        ) from exc

    digest = hashlib.sha256(raw_bytes).hexdigest()
    return LoadedUpload(
        image=loaded,
        format=detected,
        media_type=UPLOAD_IMAGE_MEDIA_TYPES[detected],
        original_width=original_width,
        original_height=original_height,
        byte_size=byte_size,
        sha256=digest,
    )
