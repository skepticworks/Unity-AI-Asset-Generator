"""Deterministic expansion of batch prompts, seeds, and variations into job specs.

A batch does not run inference. It only produces an ordered list of ordinary
generation jobs with unique seeds per prompt when sequential variation is used.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass

from unity_ai_assets.core.error_codes import FieldIssueCode
from unity_ai_assets.core.errors import (
    BatchRequestInvalidError,
    BatchTooLargeError,
    FieldIssue,
)
from unity_ai_assets.domain.enums import KNOWN_BATCH_SEED_MODES, BatchSeedMode


@dataclass(frozen=True, slots=True)
class BatchExpansionItem:
    """One expanded generation job specification."""

    index: int
    prompt_index: int
    variation_index: int
    seed: int
    prompt: str
    output_name: str


@dataclass(frozen=True, slots=True)
class BatchExpansionPlan:
    """Validated, ordered expansion used for preview and job creation."""

    items: tuple[BatchExpansionItem, ...]
    seed_mode: str
    base_seeds: tuple[int, ...]
    variation_count: int
    warnings: tuple[str, ...] = ()

    @property
    def job_count(self) -> int:
        return len(self.items)

    @property
    def prompt_count(self) -> int:
        return len({item.prompt_index for item in self.items})

    def seeds_for_prompt(self, prompt_index: int = 0) -> tuple[int, ...]:
        return tuple(item.seed for item in self.items if item.prompt_index == prompt_index)

    def seed_summary(self) -> str:
        seeds = self.seeds_for_prompt(0)
        if not seeds:
            return "No seeds"
        if len(seeds) <= 12:
            return ", ".join(str(seed) for seed in seeds)
        return f"{seeds[0]}…{seeds[-1]} ({len(seeds)} unique seeds per prompt)"


def build_output_name(
    base: str,
    *,
    prompt_index: int,
    seed: int,
    variation_index: int,
    max_length: int,
) -> str:
    """Build a predictable, collision-safe output stem for one expanded job."""
    stem = (base or "texture").strip() or "texture"
    suffix = f"_p{prompt_index:02d}_s{seed}_v{variation_index:02d}"
    if len(suffix) >= max_length:
        return suffix[-max_length:]
    room = max_length - len(suffix)
    trimmed = stem[:room].rstrip("_-.")
    if not trimmed:
        trimmed = "tex"
        if len(trimmed) + len(suffix) > max_length:
            return suffix[-max_length:]
    return trimmed + suffix


def _issue(message: str, *, actual: object = None) -> FieldIssue:
    return FieldIssue(code=FieldIssueCode.VALUE_INVALID, message=message, actual=actual)


def _required(message: str) -> FieldIssue:
    return FieldIssue(code=FieldIssueCode.FIELD_REQUIRED, message=message)


def normalize_prompts(
    prompts: list[str],
    *,
    max_prompts: int,
    max_prompt_length: int,
) -> list[str]:
    """Strip and validate prompt entries, preserving caller order."""
    if not prompts:
        raise BatchRequestInvalidError(
            "At least one prompt is required.",
            field_issues={"prompts": [_required("At least one prompt is required.")]},
        )
    if len(prompts) > max_prompts:
        raise BatchRequestInvalidError(
            f"A batch may include at most {max_prompts} prompts.",
            field_issues={
                "prompts": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                        message=f"A batch may include at most {max_prompts} prompts.",
                        actual=len(prompts),
                        maximum=max_prompts,
                    )
                ]
            },
        )
    normalized: list[str] = []
    issues: dict[str, list[FieldIssue]] = {}
    for index, raw in enumerate(prompts):
        text = " ".join(str(raw or "").split())
        field = f"prompts.{index}"
        if not text:
            issues[field] = [_required("Prompt must not be empty.")]
            continue
        if len(text) > max_prompt_length:
            issues[field] = [
                FieldIssue(
                    code=FieldIssueCode.VALUE_TOO_LONG,
                    message=f"Prompt exceeds the maximum length of {max_prompt_length}.",
                    actual=len(text),
                    maximum=max_prompt_length,
                )
            ]
            continue
        normalized.append(text)
    if issues:
        raise BatchRequestInvalidError(
            "One or more prompt entries are invalid.",
            field_issues=issues,
        )
    return normalized


def resolve_base_seeds(
    *,
    seed_mode: str,
    seed: int | None,
    seed_start: int | None,
    seed_end: int | None,
    variation_count: int,
    min_seed: int,
    max_seed: int,
    random_seed_factory: Callable[[int, int], int] | None = None,
) -> tuple[int, ...]:
    """Resolve the base seed list used before variation offsets."""
    mode = (seed_mode or "").strip().lower()
    if mode not in KNOWN_BATCH_SEED_MODES:
        raise BatchRequestInvalidError(
            "seed_mode must be fixed, random, or sequential.",
            field_issues={
                "seed_mode": [
                    _issue(
                        "seed_mode must be fixed, random, or sequential.",
                        actual=seed_mode,
                    )
                ]
            },
        )
    if variation_count < 1:
        raise BatchRequestInvalidError(
            "variation_count must be at least 1.",
            field_issues={
                "variation_count": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_BELOW_MINIMUM,
                        message="variation_count must be at least 1.",
                        actual=variation_count,
                        minimum=1,
                    )
                ]
            },
        )

    def _in_range(value: int, field_name: str) -> None:
        if value < min_seed or value > max_seed:
            raise BatchRequestInvalidError(
                f"{field_name} is outside the allowed seed range.",
                field_issues={
                    field_name: [
                        FieldIssue(
                            code=FieldIssueCode.VALUE_INVALID,
                            message=f"{field_name} must be between {min_seed} and {max_seed}.",
                            actual=value,
                            minimum=min_seed,
                            maximum=max_seed,
                        )
                    ]
                },
            )

    if mode == BatchSeedMode.SEQUENTIAL.value:
        if seed_start is None or seed_end is None:
            raise BatchRequestInvalidError(
                "Sequential seed mode requires seed_start and seed_end.",
                field_issues={
                    "seed_start": [_required("seed_start is required for sequential mode.")],
                    "seed_end": [_required("seed_end is required for sequential mode.")],
                },
            )
        start = int(seed_start)
        end = int(seed_end)
        _in_range(start, "seed_start")
        _in_range(end, "seed_end")
        if start > end:
            raise BatchRequestInvalidError(
                "seed_start must be less than or equal to seed_end.",
                field_issues={
                    "seed_start": [
                        _issue("seed_start must be less than or equal to seed_end.", actual=start)
                    ]
                },
            )
        return tuple(range(start, end + 1))

    if mode == BatchSeedMode.FIXED.value:
        if seed is None:
            raise BatchRequestInvalidError(
                "Fixed seed mode requires a seed.",
                field_issues={"seed": [_required("seed is required for fixed mode.")]},
            )
        resolved = int(seed)
        _in_range(resolved, "seed")
        return (resolved,)

    if seed is not None:
        resolved = int(seed)
        _in_range(resolved, "seed")
        return (resolved,)
    factory = random_seed_factory or (
        lambda low, high: secrets.randbelow(high - low + 1) + low
    )
    span = max(0, variation_count - 1)
    high = max_seed - span
    if high < min_seed:
        raise BatchRequestInvalidError(
            "variation_count is too large to fit in the allowed seed range.",
            field_issues={
                "variation_count": [
                    _issue(
                        "variation_count is too large to fit in the allowed seed range.",
                        actual=variation_count,
                    )
                ]
            },
        )
    return (int(factory(min_seed, high)),)


def expand_batch(
    prompts: list[str],
    *,
    seed_mode: str,
    variation_count: int,
    seed: int | None = None,
    seed_start: int | None = None,
    seed_end: int | None = None,
    output_name: str = "texture",
    min_seed: int = 0,
    max_seed: int = 2**32 - 1,
    max_jobs: int = 32,
    max_prompts: int = 50,
    max_variations: int = 16,
    max_prompt_length: int = 2000,
    max_output_name_length: int = 100,
    random_seed_factory: Callable[[int, int], int] | None = None,
) -> BatchExpansionPlan:
    """Expand prompts × base seeds × variations into deterministic job specs."""
    normalized = normalize_prompts(
        prompts,
        max_prompts=max_prompts,
        max_prompt_length=max_prompt_length,
    )
    if variation_count > max_variations:
        raise BatchRequestInvalidError(
            f"variation_count may be at most {max_variations}.",
            field_issues={
                "variation_count": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                        message=f"variation_count may be at most {max_variations}.",
                        actual=variation_count,
                        maximum=max_variations,
                    )
                ]
            },
        )
    base_seeds = resolve_base_seeds(
        seed_mode=seed_mode,
        seed=seed,
        seed_start=seed_start,
        seed_end=seed_end,
        variation_count=variation_count,
        min_seed=min_seed,
        max_seed=max_seed,
        random_seed_factory=random_seed_factory,
    )
    stride = len(base_seeds)
    job_count = len(normalized) * stride * variation_count
    if job_count > max_jobs:
        raise BatchTooLargeError(
            f"This batch would create {job_count} jobs, which exceeds the maximum of {max_jobs}.",
            details={"job_count": job_count, "maximum": max_jobs},
            field_issues={
                "batch": [
                    FieldIssue(
                        code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                        message=(
                            f"This batch would create {job_count} jobs "
                            f"(maximum {max_jobs}). Reduce prompts, seed range, or variations."
                        ),
                        actual=job_count,
                        maximum=max_jobs,
                    )
                ]
            },
        )

    items: list[BatchExpansionItem] = []
    warnings: list[str] = []
    seen_prompt_text: set[str] = set()
    for prompt_index, prompt in enumerate(normalized):
        if prompt in seen_prompt_text:
            warnings.append(
                f"Prompt {prompt_index} duplicates an earlier entry and reuses the same seeds."
            )
        seen_prompt_text.add(prompt)
        used_seeds: set[int] = set()
        for base in base_seeds:
            for variation_index in range(variation_count):
                actual_seed = base + variation_index * stride
                if actual_seed > max_seed:
                    raise BatchRequestInvalidError(
                        "Expanded seed exceeds the allowed maximum. "
                        "Reduce the sequential range or variation count.",
                        field_issues={
                            "seed": [
                                FieldIssue(
                                    code=FieldIssueCode.VALUE_ABOVE_MAXIMUM,
                                    message="Expanded seed exceeds the allowed maximum.",
                                    actual=actual_seed,
                                    maximum=max_seed,
                                )
                            ]
                        },
                    )
                if actual_seed in used_seeds:
                    raise BatchRequestInvalidError(
                        "Sequential seed expansion produced a duplicate seed for the same prompt.",
                        field_issues={
                            "seed": [
                                _issue(
                                    "Sequential seed expansion produced a duplicate seed.",
                                    actual=actual_seed,
                                )
                            ]
                        },
                    )
                used_seeds.add(actual_seed)
                items.append(
                    BatchExpansionItem(
                        index=len(items),
                        prompt_index=prompt_index,
                        variation_index=variation_index,
                        seed=actual_seed,
                        prompt=prompt,
                        output_name=build_output_name(
                            output_name,
                            prompt_index=prompt_index,
                            seed=actual_seed,
                            variation_index=variation_index,
                            max_length=max_output_name_length,
                        ),
                    )
                )
    return BatchExpansionPlan(
        items=tuple(items),
        seed_mode=(seed_mode or "").strip().lower(),
        base_seeds=base_seeds,
        variation_count=variation_count,
        warnings=tuple(warnings),
    )
