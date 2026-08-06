"""Unit tests for GenerationService validation and seed handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from unity_ai_assets.core.config import Settings
from unity_ai_assets.core.errors import GenerationRequestInvalidError, InferenceError
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.services.generation_service import GenerationService
from unity_ai_assets.services.output_service import OutputService


@pytest.fixture
def service(tmp_path: Path) -> tuple[GenerationService, FakeImageGenerationBackend]:
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        output_directory=tmp_path / "generated",
        max_width=1024,
        max_height=1024,
    )
    (tmp_path / "generated").mkdir()
    backend = FakeImageGenerationBackend()
    output = OutputService(
        settings.output_directory,
        app_version="0.3.0",
        model_family="sd15",
        max_output_name_length=settings.max_output_name_length,
    )
    return GenerationService(backend, output, settings), backend


def test_explicit_seed_preserved(
    service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = service
    result = gen.generate_texture(prompt="wall", seed=12345, width=64, height=64, steps=1)
    assert result.seed == 12345
    assert backend.calls[0].seed == 12345


def test_random_seed_assigned_when_omitted(
    service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = service
    result = gen.generate_texture(prompt="wall", width=64, height=64, steps=1)
    assert isinstance(result.seed, int)
    assert 0 <= result.seed < 2**32
    assert backend.calls[0].seed == result.seed


def test_invalid_dimensions_not_divisible_by_eight(
    service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = service
    with pytest.raises(GenerationRequestInvalidError) as exc_info:
        gen.generate_texture(prompt="wall", width=500, height=512)
    assert "width" in exc_info.value.field_issues


def test_excessive_dimensions(
    service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = service
    with pytest.raises(GenerationRequestInvalidError) as exc_info:
        gen.generate_texture(prompt="wall", width=2048, height=512)
    assert exc_info.value.field_issues["width"][0].code.value == "VALUE_ABOVE_MAXIMUM"


def test_missing_prompt(
    service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, _ = service
    with pytest.raises(GenerationRequestInvalidError):
        gen.generate_texture(prompt="   ")


def test_backend_failure_translation(tmp_path: Path) -> None:
    settings = Settings(
        model_id="fake/test-model",
        device="cpu",
        output_directory=tmp_path / "generated",
    )
    (tmp_path / "generated").mkdir()
    backend = FakeImageGenerationBackend(fail=True)
    output = OutputService(settings.output_directory, app_version="0.3.0")
    gen = GenerationService(backend, output, settings)
    with pytest.raises(InferenceError):
        gen.generate_texture(prompt="wall", width=64, height=64, steps=1)


def test_backend_substitution_uses_injected_backend(
    service: tuple[GenerationService, FakeImageGenerationBackend],
) -> None:
    gen, backend = service
    gen.generate_texture(prompt="substitute-me", width=32, height=32, steps=1, seed=7)
    assert len(backend.calls) == 1
    assert backend.calls[0].prompt == "substitute-me"
