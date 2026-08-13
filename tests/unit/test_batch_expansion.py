"""Unit tests for deterministic batch prompt/seed/variation expansion."""

from __future__ import annotations

import pytest

from unity_ai_assets.core.errors import BatchRequestInvalidError, BatchTooLargeError
from unity_ai_assets.domain.batches import (
    BatchRecord,
    aggregate_batch_state,
    count_job_states,
)
from unity_ai_assets.domain.enums import BatchState, JobState
from unity_ai_assets.domain.jobs import JobError, JobRecord, utc_now_iso
from unity_ai_assets.services.batch_expansion import (
    build_output_name,
    expand_batch,
    resolve_base_seeds,
)


def test_prompt_and_variation_expansion_is_ordered_and_deterministic() -> None:
    first = expand_batch(
        ["rusty plate", "mossy brick"],
        seed_mode="fixed",
        seed=10,
        variation_count=2,
        output_name="wall",
    )
    second = expand_batch(
        ["rusty plate", "mossy brick"],
        seed_mode="fixed",
        seed=10,
        variation_count=2,
        output_name="wall",
    )
    assert first.job_count == 4
    assert [(item.prompt, item.seed, item.variation_index) for item in first.items] == [
        ("rusty plate", 10, 0),
        ("rusty plate", 11, 1),
        ("mossy brick", 10, 0),
        ("mossy brick", 11, 1),
    ]
    assert [item.index for item in first.items] == [0, 1, 2, 3]
    assert first.items == second.items
    assert first.items[0].output_name == "wall_p00_s10_v00"
    assert first.items[1].output_name == "wall_p00_s11_v01"


def test_sequential_seed_range_avoids_duplicate_seeds() -> None:
    plan = expand_batch(
        ["metal"],
        seed_mode="sequential",
        seed_start=10,
        seed_end=12,
        variation_count=2,
    )
    seeds = [item.seed for item in plan.items]
    assert seeds == [10, 13, 11, 14, 12, 15]
    assert len(seeds) == len(set(seeds))
    assert plan.seed_summary() == "10, 13, 11, 14, 12, 15"


def test_random_seed_uses_provided_or_factory() -> None:
    plan = expand_batch(
        ["a", "b"],
        seed_mode="random",
        variation_count=3,
        random_seed_factory=lambda _low, _high: 42,
    )
    assert plan.base_seeds == (42,)
    assert [item.seed for item in plan.items] == [42, 43, 44, 42, 43, 44]
    explicit = expand_batch(["a"], seed_mode="random", seed=9, variation_count=1)
    assert explicit.base_seeds == (9,)


def test_empty_and_excessive_configurations_are_rejected() -> None:
    with pytest.raises(BatchRequestInvalidError, match="At least one prompt"):
        expand_batch([], seed_mode="fixed", seed=1, variation_count=1)
    with pytest.raises(BatchRequestInvalidError, match="invalid"):
        expand_batch(["  "], seed_mode="fixed", seed=1, variation_count=1)
    with pytest.raises(BatchRequestInvalidError, match="seed_start"):
        expand_batch(["ok"], seed_mode="sequential", variation_count=1)
    with pytest.raises(BatchRequestInvalidError, match="less than or equal"):
        expand_batch(
            ["ok"], seed_mode="sequential", seed_start=9, seed_end=3, variation_count=1
        )
    with pytest.raises(BatchTooLargeError, match="exceeds the maximum"):
        expand_batch(
            ["a", "b", "c"],
            seed_mode="sequential",
            seed_start=1,
            seed_end=10,
            variation_count=2,
            max_jobs=4,
        )
    with pytest.raises(BatchRequestInvalidError, match="at most"):
        expand_batch(["x"], seed_mode="fixed", seed=1, variation_count=8, max_variations=4)


def test_img2img_style_prompts_preserve_order_after_normalization() -> None:
    plan = expand_batch(
        ["  weathered rust  ", "clean bronze"],
        seed_mode="fixed",
        seed=5,
        variation_count=1,
    )
    assert [item.prompt for item in plan.items] == ["weathered rust", "clean bronze"]
    assert plan.items[0].prompt_index == 0
    assert plan.items[1].prompt_index == 1


def test_output_name_is_truncated_to_max_length() -> None:
    name = build_output_name(
        "very_long_texture_name_that_should_be_clipped",
        prompt_index=0,
        seed=123456,
        variation_index=0,
        max_length=24,
    )
    assert len(name) <= 24
    assert name.endswith("_s123456_v00")


def test_resolve_base_seeds_fixed_and_sequential() -> None:
    assert resolve_base_seeds(
        seed_mode="fixed",
        seed=7,
        seed_start=None,
        seed_end=None,
        variation_count=1,
        min_seed=0,
        max_seed=100,
    ) == (7,)
    assert resolve_base_seeds(
        seed_mode="sequential",
        seed=None,
        seed_start=3,
        seed_end=5,
        variation_count=1,
        min_seed=0,
        max_seed=100,
    ) == (3, 4, 5)


def _job(
    job_id: str,
    state: JobState,
    *,
    retryable: bool = True,
    batch_index: int = 0,
) -> JobRecord:
    error = None
    if state in {JobState.FAILED, JobState.CANCELLED, JobState.INTERRUPTED}:
        error = JobError(
            code="INFERENCE_FAILED" if retryable else "GENERATION_REQUEST_INVALID",
            message="failed",
            retryable=retryable,
            occurred_at=utc_now_iso(),
        )
    return JobRecord(
        job_id=job_id,
        state=state,
        generation_type="text_to_image",
        asset_type="texture",
        request={"prompt": "x"},
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
        error=error,
        batch_id="batch",
        batch_index=batch_index,
        prompt_index=0,
        variation_index=0,
    )


def test_batch_state_aggregation_distinguishes_partial_failure() -> None:
    completed = _job("1" * 32, JobState.COMPLETED, batch_index=0)
    completed.job_id = "11111111-1111-1111-1111-111111111111"
    failed = _job("2" * 32, JobState.FAILED, batch_index=1)
    failed.job_id = "22222222-2222-2222-2222-222222222222"
    queued = _job("3" * 32, JobState.QUEUED, batch_index=2)
    queued.job_id = "33333333-3333-3333-3333-333333333333"
    assert aggregate_batch_state([completed, failed]) is BatchState.PARTIAL_SUCCESS
    assert aggregate_batch_state([failed, failed]) is BatchState.FAILED
    assert aggregate_batch_state([completed, completed]) is BatchState.COMPLETED
    cancelled = _job("4" * 32, JobState.CANCELLED, batch_index=3)
    cancelled.job_id = "44444444-4444-4444-4444-444444444444"
    assert aggregate_batch_state([cancelled, cancelled]) is BatchState.CANCELLED
    assert aggregate_batch_state([queued, completed]) is BatchState.QUEUED
    running = _job("5" * 32, JobState.RUNNING, batch_index=4)
    running.job_id = "55555555-5555-5555-5555-555555555555"
    assert aggregate_batch_state([running, queued]) is BatchState.RUNNING
    assert (
        aggregate_batch_state([queued], cancel_requested=True) is BatchState.CANCELLING
    )
    counts = count_job_states([completed, failed, cancelled])
    assert counts.completed == 1
    assert counts.failed == 1
    assert counts.cancelled == 1
    assert counts.terminal == 3


def test_batch_record_round_trip_preserves_job_ids() -> None:
    record = BatchRecord(
        batch_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:01Z",
        seed_mode="fixed",
        variation_count=2,
        prompts=["one", "two"],
        job_ids=["11111111-1111-1111-1111-111111111111"],
        seed=9,
        resolved_base_seeds=[9],
        generation_profile_id="ps1_environment_texture",
        request_template={"width": 32, "source_image": {"present": True}},
    )
    restored = BatchRecord.from_dict(record.to_dict())
    assert restored.batch_id == record.batch_id
    assert restored.job_ids == record.job_ids
    assert restored.prompts == ["one", "two"]
    assert restored.request_template["width"] == 32
