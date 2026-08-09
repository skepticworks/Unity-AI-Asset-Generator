"""Deterministic alpha-channel cleanup for sprite/icon RGBA images."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode, FieldIssueCode
from unity_ai_assets.core.errors import AppError, FieldIssue


@dataclass(frozen=True, slots=True)
class AlphaCleanupParams:
    """Configurable alpha cleanup parameters (all applied deterministically)."""

    alpha_threshold: int = 16
    alpha_feather: int = 0
    remove_near_transparent: bool = True
    zero_rgb_when_transparent: bool = True

    def validated(self) -> AlphaCleanupParams:
        """Return self after range checks; raise on invalid values."""
        issues: dict[str, list[FieldIssue]] = {}
        if not 0 <= self.alpha_threshold <= 255:
            issues["alpha_threshold"] = [
                FieldIssue(
                    code=FieldIssueCode.VALUE_INVALID,
                    message="alpha_threshold must be an integer from 0 to 255.",
                    actual=self.alpha_threshold,
                    minimum=0,
                    maximum=255,
                )
            ]
        if not 0 <= self.alpha_feather <= 64:
            issues["alpha_feather"] = [
                FieldIssue(
                    code=FieldIssueCode.VALUE_INVALID,
                    message="alpha_feather must be an integer from 0 to 64.",
                    actual=self.alpha_feather,
                    minimum=0,
                    maximum=64,
                )
            ]
        if issues:
            raise AppError(
                "Invalid alpha cleanup parameters.",
                code=AppErrorCode.ALPHA_PROCESSING_FAILED,
                field_issues=issues,
            )
        return self


def apply_alpha_cleanup(image: Image.Image, params: AlphaCleanupParams) -> Image.Image:
    """Apply deterministic alpha cleanup while preserving dimensions and RGBA mode.

    Steps:
    1. Convert to RGBA without resizing.
    2. When ``remove_near_transparent`` is true, hard-threshold alpha below
       ``alpha_threshold`` to 0.
    3. When ``alpha_feather`` > 0, linearly ramp alpha from threshold to
       ``threshold + feather`` (edge soft cleanup without resizing).
    4. Optionally zero RGB for fully transparent pixels.
    """
    params = params.validated()
    try:
        rgba = image.convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "Failed to convert image to RGBA for alpha cleanup.",
            code=AppErrorCode.ALPHA_PROCESSING_FAILED,
        ) from exc

    width, height = rgba.size
    pixels = list(rgba.getdata())
    threshold = params.alpha_threshold
    feather = params.alpha_feather
    soft_end = threshold + feather

    cleaned: list[tuple[int, int, int, int]] = []
    for r, g, b, a in pixels:
        new_a = a
        if params.remove_near_transparent:
            if a < threshold:
                new_a = 0
            elif feather > 0 and a < soft_end:
                # Linear ramp from 0 at threshold to original at soft_end.
                span = soft_end - threshold
                new_a = int(round((a - threshold) * a / span)) if span > 0 else a
                new_a = max(0, min(255, new_a))

        if params.zero_rgb_when_transparent and new_a == 0:
            cleaned.append((0, 0, 0, 0))
        else:
            cleaned.append((r, g, b, new_a))

    try:
        result = Image.new("RGBA", (width, height))
        result.putdata(cleaned)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "Failed while writing cleaned alpha channel.",
            code=AppErrorCode.ALPHA_PROCESSING_FAILED,
        ) from exc

    if result.size != (width, height):
        raise AppError(
            "Alpha cleanup changed image dimensions.",
            code=AppErrorCode.ALPHA_PROCESSING_FAILED,
        )
    return result
