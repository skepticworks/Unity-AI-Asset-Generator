"""Deterministic, lightweight seam analysis for tileable textures."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from unity_ai_assets.processing.seam_thresholds import (
    SEAM_EDGE_PERCENTILE,
    SEAM_RGB_NORMALIZER,
    SEAM_SCORE_ACCEPTABLE_MAX,
    SEAM_SCORE_EXCELLENT_MAX,
)


@dataclass(frozen=True, slots=True)
class SeamAnalysisResult:
    """Objective seam diagnostics (not a perceptual guarantee)."""

    horizontal_mean: float
    horizontal_max: float
    horizontal_percentile: float
    horizontal_score: float
    vertical_mean: float
    vertical_max: float
    vertical_percentile: float
    vertical_score: float
    combined_score: float

    @property
    def quality_label(self) -> str:
        if self.combined_score <= SEAM_SCORE_EXCELLENT_MAX:
            return "excellent"
        if self.combined_score <= SEAM_SCORE_ACCEPTABLE_MAX:
            return "acceptable"
        return "poor"


def _as_rgba_pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    rgba = image.convert("RGBA")
    return list(rgba.getdata())


def _rgb_distance(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    # Alpha-aware: when both nearly transparent, treat as matching.
    if a[3] < 8 and b[3] < 8:
        return 0.0
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])) / 3.0


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (percentile / 100.0) * (len(sorted_values) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    frac = rank - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


def _edge_stats(distances: list[float]) -> tuple[float, float, float, float]:
    if not distances:
        return 0.0, 0.0, 0.0, 0.0
    mean = sum(distances) / len(distances)
    maximum = max(distances)
    ordered = sorted(distances)
    percentile = _percentile(ordered, SEAM_EDGE_PERCENTILE)
    score = min(1.0, mean / SEAM_RGB_NORMALIZER)
    return mean, maximum, percentile, score


def analyze_seams(image: Image.Image) -> SeamAnalysisResult:
    """Compare left/right and top/bottom edges; return normalized scores in ``[0, 1]``.

    Lower scores indicate closer edge agreement. Scores are objective diagnostics only.
    """
    width, height = image.size
    if width < 2 or height < 2:
        raise ValueError("image must be at least 2x2 for seam analysis")

    pixels = _as_rgba_pixels(image)

    def at(x: int, y: int) -> tuple[int, int, int, int]:
        return pixels[y * width + x]

    horizontal_distances = [_rgb_distance(at(0, y), at(width - 1, y)) for y in range(height)]
    vertical_distances = [_rgb_distance(at(x, 0), at(x, height - 1)) for x in range(width)]

    h_mean, h_max, h_pct, h_score = _edge_stats(horizontal_distances)
    v_mean, v_max, v_pct, v_score = _edge_stats(vertical_distances)
    combined = (h_score + v_score) / 2.0

    return SeamAnalysisResult(
        horizontal_mean=h_mean,
        horizontal_max=h_max,
        horizontal_percentile=h_pct,
        horizontal_score=h_score,
        vertical_mean=v_mean,
        vertical_max=v_max,
        vertical_percentile=v_pct,
        vertical_score=v_score,
        combined_score=combined,
    )
