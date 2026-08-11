"""Lightweight fake backend for tests (no model download, no GPU)."""

from __future__ import annotations

import time
from collections.abc import Callable

from PIL import Image

from unity_ai_assets.core.errors import InferenceError
from unity_ai_assets.domain.capabilities import InferenceCapabilities
from unity_ai_assets.domain.enums import AssetType
from unity_ai_assets.domain.generation import GeneratedImage, GenerationRequest


class FakeImageGenerationBackend:
    """Deterministic in-memory backend used by automated tests."""

    def __init__(
        self,
        *,
        device_name: str = "cpu",
        model_id: str = "fake/test-model",
        model_revision: str | None = "test-revision",
        fail: bool = False,
        delay_seconds: float = 0.01,
        color_factory: Callable[[GenerationRequest], tuple[int, int, int]] | None = None,
        model_loaded: bool = True,
        resolved_precision: str = "float32",
        default_scheduler: str = "pndm",
    ) -> None:
        self._device_name = device_name
        self._model_id = model_id
        self._model_revision = model_revision
        self._fail = fail
        self._delay_seconds = delay_seconds
        self._color_factory = color_factory or self._default_color
        self._loaded = model_loaded
        self._resolved_precision = resolved_precision
        self._default_scheduler = default_scheduler
        self.calls: list[GenerationRequest] = []
        self.capability_calls: int = 0
        self.unload_calls: int = 0

    @staticmethod
    def _default_color(request: GenerationRequest) -> tuple[int, int, int]:
        # Stable RGB derived from seed for easy assertions.
        seed = request.seed & 0xFFFFFF
        return ((seed >> 16) & 0xFF, (seed >> 8) & 0xFF, seed & 0xFF)

    @property
    def model_loaded(self) -> bool:
        return self._loaded

    @property
    def device_name(self) -> str:
        return self._device_name

    def unload_weights(self) -> bool:
        self.unload_calls += 1
        if not self._loaded:
            return False
        self._loaded = False
        return True

    def describe_capabilities(self) -> InferenceCapabilities:
        self.capability_calls += 1
        return InferenceCapabilities(
            text_to_image_supported=True,
            image_to_image_supported=False,
            inpainting_supported=False,
            supported_asset_types=[
                AssetType.TEXTURE.value,
                AssetType.SPRITE.value,
                AssetType.ICON.value,
            ],
            scheduler_selection_supported=False,
            default_scheduler=self._default_scheduler,
            available_schedulers=[],
            available_precisions=["float32"],
            precision_user_selectable=False,
            model_loaded=self._loaded,
            resolved_device=self._device_name,
            resolved_precision=self._resolved_precision,
        )

    def generate(self, request: GenerationRequest) -> GeneratedImage:
        self.calls.append(request)
        if self._fail:
            raise InferenceError("Fake backend forced failure")

        started = time.perf_counter()
        time.sleep(self._delay_seconds)
        color = self._color_factory(request)
        image = Image.new("RGB", (request.width, request.height), color=color)
        elapsed = time.perf_counter() - started
        self._loaded = True
        return GeneratedImage(
            image=image,
            seed=request.seed,
            width=request.width,
            height=request.height,
            elapsed_seconds=round(elapsed, 4),
            device=self._device_name,
            torch_dtype=self._resolved_precision,
            model_id=self._model_id,
            model_revision=self._model_revision,
        )
