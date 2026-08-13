"""Execution-backend abstraction for generation jobs.

The job system owns orchestration and state. Implementations perform generation
without exposing local GPU vs remote worker details to the API or Unity client.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from unity_ai_assets.core.errors import GenerationCancelledError
from unity_ai_assets.domain.jobs import JobProgress, JobRecord, JobResult
from unity_ai_assets.services.generation_service import GenerationService

ProgressCallback = Callable[[JobProgress], None]


@runtime_checkable
class GenerationJobExecutor(Protocol):
    """Runs one generation job to completion or a safe cancellation point."""

    def validate(self, payload: dict[str, Any]) -> int:
        """Authoritative request validation. Returns the resolved seed."""
        ...

    def execute(
        self,
        job: JobRecord,
        *,
        cancel_event: threading.Event,
        on_progress: ProgressCallback,
    ) -> JobResult:
        """Execute generation. Must not publish outputs after cancellation."""
        ...


def generation_kwargs_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a stored/API generation payload to GenerationService kwargs."""
    source = payload.get("source_image")
    mask = payload.get("mask_image")
    source_dict = source if isinstance(source, dict) else None
    mask_dict = mask if isinstance(mask, dict) else None
    return {
        "prompt": payload.get("prompt") or "",
        "negative_prompt": payload.get("negative_prompt") or "",
        "width": payload.get("width", 512),
        "height": payload.get("height", 512),
        "steps": payload.get("steps"),
        "guidance_scale": payload.get("guidance_scale"),
        "seed": payload.get("seed"),
        "output_name": payload.get("output_name") or "texture",
        "generation_profile_id": payload.get("generation_profile_id"),
        "generation_profile_revision": payload.get("generation_profile_revision"),
        "profile_origin": payload.get("profile_origin"),
        "prompt_template_id": payload.get("prompt_template_id"),
        "prompt_template_revision": payload.get("prompt_template_revision"),
        "negative_prompt_profile_id": payload.get("negative_prompt_profile_id"),
        "negative_prompt_profile_revision": payload.get("negative_prompt_profile_revision"),
        "unity_import_profile_id": payload.get("unity_import_profile_id"),
        "asset_type": payload.get("asset_type") or "texture",
        "transparency_strategy": payload.get("transparency_strategy"),
        "alpha_threshold": payload.get("alpha_threshold"),
        "alpha_feather": payload.get("alpha_feather"),
        "remove_near_transparent": payload.get("remove_near_transparent"),
        "zero_rgb_when_transparent": payload.get("zero_rgb_when_transparent"),
        "pixels_per_unit": payload.get("pixels_per_unit"),
        "pivot_mode": payload.get("pivot_mode"),
        "custom_pivot_x": payload.get("custom_pivot_x"),
        "custom_pivot_y": payload.get("custom_pivot_y"),
        "atlas_hint": payload.get("atlas_hint"),
        "tileable": payload.get("tileable"),
        "apply_seam_correction": payload.get("apply_seam_correction"),
        "seam_blend_width": payload.get("seam_blend_width"),
        "palette_reduction_enabled": payload.get("palette_reduction_enabled"),
        "palette_color_count": payload.get("palette_color_count"),
        "operation": payload.get("operation"),
        "source_image_base64": None if source_dict is None else source_dict.get("content_base64"),
        "source_image_media_type": None if source_dict is None else source_dict.get("media_type"),
        "mask_image_base64": None if mask_dict is None else mask_dict.get("content_base64"),
        "mask_image_media_type": None if mask_dict is None else mask_dict.get("media_type"),
        "denoising_strength": payload.get("denoising_strength"),
    }


class LocalGenerationExecutor:
    """Runs jobs through the existing local GenerationService / GPU pipeline."""

    def __init__(self, generation_service: GenerationService) -> None:
        self._generation_service = generation_service

    def validate(self, payload: dict[str, Any]) -> int:
        kwargs = generation_kwargs_from_payload(payload)
        return self._generation_service.validate_texture_request(**kwargs)

    def execute(
        self,
        job: JobRecord,
        *,
        cancel_event: threading.Event,
        on_progress: ProgressCallback,
    ) -> JobResult:
        if cancel_event.is_set():
            raise GenerationCancelledError("Job cancelled before execution started.")
        kwargs = generation_kwargs_from_payload(job.request)
        if job.seed is not None:
            kwargs["seed"] = job.seed

        def _progress(stage: str, current: int | None, total: int | None) -> None:
            messages = {
                "validating": "Validating generation request",
                "generating": "Running model inference",
                "processing": "Applying post-processing",
                "persisting": "Writing outputs",
            }
            on_progress(
                JobProgress(
                    stage=stage,
                    message=messages.get(stage, stage),
                    current_step=current,
                    total_steps=total,
                )
            )

        result = self._generation_service.generate_texture(
            **kwargs,
            cancel_event=cancel_event,
            on_progress=_progress,
        )
        if cancel_event.is_set():
            raise GenerationCancelledError("Job cancelled before result publication.")
        return JobResult(
            generation_id=result.generation_id,
            status=result.status,
            operation=result.operation,
            asset_type=result.asset_type,
            seed=result.seed,
            width=result.width,
            height=result.height,
            elapsed_seconds=result.elapsed_seconds,
            resources={
                "image": f"/api/v1/generations/{result.generation_id}/image",
                "manifest": f"/api/v1/generations/{result.generation_id}/manifest",
            },
            schema_versions={"generation_manifest": result.manifest_schema_version},
            image_path=result.image_path,
            metadata_path=result.metadata_path,
        )
