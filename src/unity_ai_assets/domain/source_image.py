"""Validation and decoding of img2img source (init) images.

The source image is the generation starting latent / init image. It is not a
reference-conditioning input (IP-Adapter, style/identity references, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.domain.generation import SourceImageMetadata
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.domain.image_upload import (
    decode_image_base64,
    load_uploaded_image,
    rgb_ignoring_alpha,
)

SUPPORTED_SOURCE_IMAGE_FORMATS: tuple[str, ...] = ("png", "jpeg", "webp")
SOURCE_IMAGE_MEDIA_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


@dataclass(frozen=True, slots=True)
class ValidatedSourceImage:
    """Decoded, policy-validated img2img init image plus original metadata."""

    image: Image.Image
    metadata: SourceImageMetadata


def decode_source_image_base64(content_base64: str) -> bytes:
    """Decode base64 source-image bytes or raise a field-level validation error."""
    return decode_image_base64(content_base64, field="source_image")


def validate_source_image(
    *,
    raw_bytes: bytes,
    policy: GenerationPolicy,
    media_type: str | None = None,
    apply_exif: bool = False,
) -> ValidatedSourceImage:
    """Validate uploaded bytes and return an RGB init image plus metadata.

    Rejects unsupported formats, oversize payloads, out-of-policy dimensions,
    and corrupt/unreadable images. Does not treat the image as reference
    conditioning.

    ``apply_exif`` is enabled for inpainting so source and mask share orientation.
    Img2img keeps the historical default (no EXIF transpose).
    """
    loaded = load_uploaded_image(
        raw_bytes=raw_bytes,
        policy=policy,
        media_type=media_type,
        field="source_image",
        maximum_bytes=policy.maximum_source_image_bytes,
        supported_formats=policy.supported_source_image_formats,
        apply_exif=apply_exif,
    )
    rgb = rgb_ignoring_alpha(loaded.image)
    if rgb is not loaded.image:
        loaded.image.close()

    metadata = SourceImageMetadata(
        format=loaded.format,
        media_type=loaded.media_type,
        original_width=loaded.original_width,
        original_height=loaded.original_height,
        byte_size=loaded.byte_size,
        sha256=loaded.sha256,
    )
    return ValidatedSourceImage(image=rgb, metadata=metadata)


def prepare_init_image(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return an RGB init image at the generation size using deterministic LANCZOS."""
    rgb = image if image.mode == "RGB" else rgb_ignoring_alpha(image)
    if rgb.size == (width, height):
        return rgb
    return rgb.resize((width, height), Image.Resampling.LANCZOS)
