"""Unit tests for alpha cleanup and background-removal processing."""

from __future__ import annotations

import pytest
from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.processing.alpha_cleanup import AlphaCleanupParams, apply_alpha_cleanup
from unity_ai_assets.processing.background_removal import (
    FakeBackgroundRemover,
    UnavailableBackgroundRemover,
    create_background_remover,
)
from unity_ai_assets.processing.pipeline import ImageProcessingPipeline


def _rgb_with_white_bg(size: tuple[int, int] = (32, 32)) -> Image.Image:
    image = Image.new("RGB", size, color=(255, 255, 255))
    for x in range(8, 24):
        for y in range(8, 24):
            image.putpixel((x, y), (20, 40, 200))
    return image


def test_fake_background_removal_preserves_dimensions_and_returns_rgba() -> None:
    remover = FakeBackgroundRemover(white_threshold=250)
    source = _rgb_with_white_bg((40, 48))
    result = remover.remove_background(source)
    assert result.mode == "RGBA"
    assert result.size == (40, 48)
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((16, 16))[3] == 255


def test_alpha_cleanup_threshold_and_zero_rgb() -> None:
    image = Image.new("RGBA", (8, 8), color=(10, 20, 30, 10))
    cleaned = apply_alpha_cleanup(
        image,
        AlphaCleanupParams(
            alpha_threshold=16,
            alpha_feather=0,
            remove_near_transparent=True,
            zero_rgb_when_transparent=True,
        ),
    )
    assert cleaned.size == (8, 8)
    assert cleaned.mode == "RGBA"
    assert cleaned.getpixel((0, 0)) == (0, 0, 0, 0)


def test_alpha_cleanup_rejects_invalid_threshold() -> None:
    with pytest.raises(AppError) as exc:
        apply_alpha_cleanup(
            Image.new("RGBA", (4, 4), color=(0, 0, 0, 255)),
            AlphaCleanupParams(alpha_threshold=300),
        )
    assert exc.value.code == AppErrorCode.ALPHA_PROCESSING_FAILED


def test_pipeline_none_strategy_leaves_rgb() -> None:
    pipeline = ImageProcessingPipeline(FakeBackgroundRemover())
    source = Image.new("RGB", (16, 16), color=(1, 2, 3))
    result = pipeline.process(
        source,
        transparency_strategy="none",
        alpha_params=AlphaCleanupParams(),
    )
    assert result.image.mode == "RGB"
    assert result.background_removal_applied is False
    assert result.original_image is None


def test_pipeline_background_removal_applies_cleanup() -> None:
    pipeline = ImageProcessingPipeline(FakeBackgroundRemover())
    result = pipeline.process(
        _rgb_with_white_bg((24, 24)),
        transparency_strategy="background_removal",
        alpha_params=AlphaCleanupParams(alpha_threshold=16),
        preserve_original=True,
    )
    assert result.image.mode == "RGBA"
    assert result.image.size == (24, 24)
    assert result.background_removal_applied is True
    assert result.alpha_cleanup_applied is True
    assert result.original_image is not None
    assert result.background_removal_implementation == "fake:white"


def test_pipeline_unavailable_background_removal() -> None:
    pipeline = ImageProcessingPipeline(UnavailableBackgroundRemover(reason="disabled for test"))
    with pytest.raises(AppError) as exc:
        pipeline.process(
            _rgb_with_white_bg(),
            transparency_strategy="background_removal",
            alpha_params=AlphaCleanupParams(),
        )
    assert exc.value.code == AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE


def test_create_background_remover_disabled() -> None:
    remover = create_background_remover(
        enabled=False, backend="rembg", model="u2net", force_fake=False
    )
    assert remover.available is False


def test_create_background_remover_force_fake() -> None:
    remover = create_background_remover(
        enabled=True, backend="rembg", model="u2net", force_fake=True
    )
    assert remover.available is True
    assert remover.implementation_id.startswith("fake")
