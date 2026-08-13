"""Safe cancellation helpers for inference pipelines."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from unity_ai_assets.core.errors import GenerationCancelledError

ProgressHook = Callable[[str, int | None, int | None], None]


def raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    """Raise when a job cancel event is set."""
    if cancel_event is not None and cancel_event.is_set():
        raise GenerationCancelledError("Inference cancelled at a pipeline step boundary.")


def pipeline_call_kwargs(
    *,
    cancel_event: threading.Event | None,
    on_progress: ProgressHook | None,
    total_steps: int,
) -> dict[str, Any]:
    """Diffusers kwargs for step-boundary cancel and truthful step progress."""
    if cancel_event is None and on_progress is None:
        return {}

    def _on_step_end(
        _pipe: object,
        step_index: int,
        _timestep: object,
        callback_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        raise_if_cancelled(cancel_event)
        if on_progress is not None:
            on_progress("generating", step_index + 1, total_steps)
        return callback_kwargs

    return {"callback_on_step_end": _on_step_end}
