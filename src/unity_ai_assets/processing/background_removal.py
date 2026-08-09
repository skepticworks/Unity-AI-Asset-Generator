"""Local background-removal abstraction (isolated from diffusion backends)."""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from PIL import Image

from unity_ai_assets.core.error_codes import AppErrorCode
from unity_ai_assets.core.errors import AppError
from unity_ai_assets.core.logging import get_logger

logger = get_logger(__name__)

# rembg / U2-Net provenance (for docs and capability reporting).
REMBG_BACKEND_ID = "rembg"
REMBG_DEFAULT_MODEL = "u2net"
REMBG_MODEL_LICENSE = "Apache-2.0"
REMBG_MODEL_SOURCE = "https://github.com/danielgatis/rembg (U^2-Net / u2net weights)"


@runtime_checkable
class ImageBackgroundRemover(Protocol):
    """Small processing interface for transparent-background production."""

    @property
    def implementation_id(self) -> str:
        """Stable identifier recorded in manifests (e.g. rembg:u2net)."""
        ...

    @property
    def available(self) -> bool:
        """Whether this remover can run without further configuration errors."""
        ...

    def remove_background(self, image: Image.Image) -> Image.Image:
        """Return an RGBA image with background removed. Dimensions preserved."""
        ...


class FakeBackgroundRemover:
    """Deterministic fake used by tests (no weights, no network).

    Treats near-white pixels (all channels >= ``white_threshold``) as background.
    """

    def __init__(
        self, *, white_threshold: int = 250, implementation_id: str = "fake:white"
    ) -> None:
        self._white_threshold = white_threshold
        self._implementation_id = implementation_id

    @property
    def implementation_id(self) -> str:
        return self._implementation_id

    @property
    def available(self) -> bool:
        return True

    def remove_background(self, image: Image.Image) -> Image.Image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        rgba = Image.new("RGBA", (width, height))
        threshold = self._white_threshold
        out: list[tuple[int, int, int, int]] = []
        for r, g, b in rgb.getdata():
            if r >= threshold and g >= threshold and b >= threshold:
                out.append((0, 0, 0, 0))
            else:
                out.append((r, g, b, 255))
        rgba.putdata(out)  # type: ignore[arg-type]
        return rgba


class UnavailableBackgroundRemover:
    """Sentinel remover when background removal is disabled or unloadable."""

    def __init__(self, *, reason: str) -> None:
        self._reason = reason

    @property
    def implementation_id(self) -> str:
        return "unavailable"

    @property
    def available(self) -> bool:
        return False

    @property
    def reason(self) -> str:
        return self._reason

    def remove_background(self, image: Image.Image) -> Image.Image:
        raise AppError(
            self._reason,
            code=AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE,
        )


class RembgBackgroundRemover:
    """Lazy, reusable rembg session wrapper.

    Loads the rembg session on first use and reuses it across requests.
    Uses ONNX Runtime under rembg — kept out of the diffusion backend abstraction.
    """

    def __init__(self, *, model_name: str = REMBG_DEFAULT_MODEL) -> None:
        self._model_name = model_name.strip() or REMBG_DEFAULT_MODEL
        self._session: object | None = None
        self._lock = threading.Lock()
        self._import_error: str | None = None

    @property
    def implementation_id(self) -> str:
        return f"{REMBG_BACKEND_ID}:{self._model_name}"

    @property
    def available(self) -> bool:
        if self._import_error is not None:
            return False
        try:
            self._ensure_session()
        except AppError:
            return False
        return self._session is not None

    def _ensure_session(self) -> object:
        if self._session is not None:
            return self._session
        with self._lock:
            if self._session is not None:
                return self._session
            try:
                from rembg import new_session
            except Exception as exc:  # noqa: BLE001
                self._import_error = (
                    "rembg is not installed or failed to import. "
                    "Install optional extra: pip install 'unity-ai-assets[background-removal]'."
                )
                logger.warning("Background removal unavailable: %s", self._import_error)
                raise AppError(
                    self._import_error,
                    code=AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE,
                ) from exc
            try:
                logger.info(
                    "Loading background-removal model lazily (backend=rembg, model=%s)",
                    self._model_name,
                )
                self._session = new_session(self._model_name)
            except Exception as exc:  # noqa: BLE001
                message = (
                    f"Failed to load background-removal model '{self._model_name}'. "
                    "Weights may be missing or the ONNX runtime failed to initialize."
                )
                self._import_error = message
                logger.warning("%s (%s)", message, type(exc).__name__)
                raise AppError(
                    message,
                    code=AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE,
                ) from exc
            return self._session

    def remove_background(self, image: Image.Image) -> Image.Image:
        session = self._ensure_session()
        try:
            from rembg import remove
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "rembg failed to import during background removal.",
                code=AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE,
            ) from exc

        width, height = image.size
        try:
            result = remove(image.convert("RGB"), session=session)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "Background removal failed while processing the generated image.",
                code=AppErrorCode.BACKGROUND_REMOVAL_FAILED,
            ) from exc

        if not isinstance(result, Image.Image):
            raise AppError(
                "Background removal returned a non-image result.",
                code=AppErrorCode.BACKGROUND_REMOVAL_FAILED,
            )
        rgba = result.convert("RGBA")
        if rgba.size != (width, height):
            # rembg should preserve size; refuse silent resizes.
            raise AppError(
                "Background removal changed image dimensions.",
                code=AppErrorCode.BACKGROUND_REMOVAL_FAILED,
            )
        return rgba


def create_background_remover(
    *,
    enabled: bool,
    backend: str,
    model: str,
    force_fake: bool = False,
) -> ImageBackgroundRemover:
    """Factory for configured background removers.

    ``force_fake`` is intended for tests. When disabled, returns an unavailable
    sentinel that raises a clear BACKGROUND_REMOVAL_UNAVAILABLE error.
    """
    if force_fake:
        return FakeBackgroundRemover()
    if not enabled:
        return UnavailableBackgroundRemover(
            reason=(
                "Background removal is disabled. Set BACKGROUND_REMOVAL_ENABLED=true "
                "to enable local rembg-based transparency processing."
            )
        )
    normalized = (backend or REMBG_BACKEND_ID).strip().lower()
    if normalized in {REMBG_BACKEND_ID, "rembg-u2net"}:
        return RembgBackgroundRemover(model_name=model or REMBG_DEFAULT_MODEL)
    if normalized == "fake":
        return FakeBackgroundRemover()
    return UnavailableBackgroundRemover(
        reason=(
            f"Unknown background-removal backend '{backend}'. "
            f"Supported backends: {REMBG_BACKEND_ID}, fake."
        )
    )
