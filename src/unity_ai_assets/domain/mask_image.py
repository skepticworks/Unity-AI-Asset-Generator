"""Validation, semantics, and alignment for inpainting masks.

Mask convention (enforced throughout the system):

* **White (255)** = region to regenerate (inpaint)
* **Black (0)** = region to keep from the source image
* Intermediate gray values are valid soft-mask strengths (closer to white
  means more regeneration)

Alpha on the mask is ignored and never treated as the inpaint region.
Source-image alpha is likewise ignored when building the init RGB image and
does not change mask semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import FieldIssue, GenerationRequestInvalidError
from unity_ai_assets.domain.generation import SourceImageMetadata
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.domain.image_upload import (
    decode_image_base64,
    invalid_upload,
    load_uploaded_image,
    luminance_ignoring_alpha,
    rgb_ignoring_alpha,
)

# Public, stable identifiers advertised in capabilities and manifests.
MASK_CONVENTION_ID = "white_inpaints"
MASK_WHITE_MEANS = "regenerate"
MASK_BLACK_MEANS = "keep"
MASK_INPAINT_VALUE = 255
MASK_KEEP_VALUE = 0
# A mask with no pixel at or above this luminance has nothing to regenerate.
_EMPTY_MASK_THRESHOLD = 1


@dataclass(frozen=True, slots=True)
class ValidatedMaskImage:
    """Decoded L-mode mask (white=inpaint) plus original-file metadata."""

    image: Image.Image
    metadata: SourceImageMetadata


def decode_mask_image_base64(content_base64: str) -> bytes:
    """Decode base64 mask bytes or raise a field-level validation error."""
    return decode_image_base64(content_base64, field="mask_image")


def validate_mask_image(
    *,
    raw_bytes: bytes,
    policy: GenerationPolicy,
    media_type: str | None = None,
) -> ValidatedMaskImage:
    """Validate uploaded mask bytes and return an L-mode mask plus metadata.

    Applies EXIF orientation, ignores alpha, and converts color channels to
    luminance so white remains the inpaint region regardless of RGB/RGBA/L input.
    """
    loaded = load_uploaded_image(
        raw_bytes=raw_bytes,
        policy=policy,
        media_type=media_type,
        field="mask_image",
        maximum_bytes=policy.maximum_mask_image_bytes,
        supported_formats=policy.supported_mask_image_formats,
        apply_exif=True,
    )
    luminance = luminance_ignoring_alpha(loaded.image)
    if luminance is not loaded.image:
        loaded.image.close()

    histogram = list(luminance.histogram())
    populated = [value for value, count in enumerate(histogram) if count]
    max_value = max(populated) if populated else 0
    if max_value < _EMPTY_MASK_THRESHOLD:
        luminance.close()
        invalid_upload(
            "mask_image",
            FieldIssueCode.VALUE_INVALID,
            (
                "The mask has no region to regenerate. Paint or upload white "
                f"(luminance {MASK_INPAINT_VALUE}) where pixels should be inpainted; "
                f"black ({MASK_KEEP_VALUE}) is kept from the source."
            ),
            actual=max_value,
        )

    metadata = SourceImageMetadata(
        format=loaded.format,
        media_type=loaded.media_type,
        original_width=loaded.original_width,
        original_height=loaded.original_height,
        byte_size=loaded.byte_size,
        sha256=loaded.sha256,
    )
    return ValidatedMaskImage(image=luminance, metadata=metadata)


def assert_source_mask_dimensions_match(
    *,
    source_width: int,
    source_height: int,
    mask_width: int,
    mask_height: int,
) -> None:
    """Reject source/mask pairs that are not pixel-aligned at their original size."""
    if source_width == mask_width and source_height == mask_height:
        return
    raise GenerationRequestInvalidError(
        "Source image and mask dimensions must match.",
        field_issues={
            "mask_image": [
                FieldIssue(
                    code=FieldIssueCode.VALUE_INVALID,
                    message=(
                        "Mask dimensions must match the source image exactly "
                        f"({source_width}x{source_height}); the mask is "
                        f"{mask_width}x{mask_height}. Resize the mask to the source "
                        "or paint a new mask over the source. The backend will not "
                        "stretch or offset a mismatched mask."
                    ),
                    actual={"width": mask_width, "height": mask_height},
                    expected_multiple=None,
                )
            ]
        },
    )


def prepare_inpaint_source(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return an RGB init image at the generation size using deterministic LANCZOS.

    Source alpha is composited on black and then discarded. It does not affect
    the mask. Resizing is explicit: only performed when the decoded size differs
    from the requested generation size.
    """
    rgb = rgb_ignoring_alpha(image)
    if rgb.size == (width, height):
        return rgb
    return rgb.resize((width, height), Image.Resampling.LANCZOS)


def prepare_inpaint_mask(image: Image.Image, width: int, height: int) -> Image.Image:
    """Return an L-mode mask at the generation size.

    Uses LANCZOS so soft (gray) edges remain predictable after resize. Values
    stay in 0–255 with white meaning regenerate. Alpha is never consulted.
    """
    luminance = image if image.mode == "L" else luminance_ignoring_alpha(image)
    if luminance.size == (width, height):
        return luminance
    resized = luminance.resize((width, height), Image.Resampling.LANCZOS)
    return resized
