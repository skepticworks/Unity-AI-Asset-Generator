"""Deterministic generation-profile serialization."""

from __future__ import annotations

import json
from typing import Any

from unity_ai_assets.profiles.constants import GENERATION_PROFILE_SCHEMA_NAME
from unity_ai_assets.profiles.models import GenerationProfile


def generation_profile_to_dict(profile: GenerationProfile) -> dict[str, Any]:
    """Convert a profile to its canonical round-tripable JSON shape."""
    defaults = profile.generation_defaults
    return {
        "schema": {"name": GENERATION_PROFILE_SCHEMA_NAME, "version": profile.schema_version},
        "profile": {
            "id": profile.id,
            "revision": profile.revision,
            "display_name": profile.display_name,
            "description": profile.description,
            "asset_type": profile.asset_type,
            "builtin": profile.builtin,
            "tags": list(profile.tags),
        },
        "prompt": {
            "template_id": profile.template_id,
            "template_revision": profile.template_revision,
            "default_modifiers": list(profile.default_modifiers),
        },
        "negative_prompt": {
            "profile_id": profile.negative_prompt_profile_id,
            "profile_revision": profile.negative_prompt_profile_revision,
            "additional_terms": list(profile.additional_negative_terms),
        },
        "generation_defaults": {
            "width": defaults.width,
            "height": defaults.height,
            "steps": defaults.steps,
            "guidance_scale": defaults.guidance_scale,
            "seed_strategy": defaults.seed_strategy,
            "fixed_seed": defaults.fixed_seed,
            "transparency_strategy": defaults.transparency_strategy,
            "alpha_threshold": defaults.alpha_threshold,
            "alpha_feather": defaults.alpha_feather,
            "remove_near_transparent": defaults.remove_near_transparent,
            "zero_rgb_when_transparent": defaults.zero_rgb_when_transparent,
            "pixels_per_unit": defaults.pixels_per_unit,
            "pivot_mode": defaults.pivot_mode,
            "custom_pivot_x": defaults.custom_pivot_x,
            "custom_pivot_y": defaults.custom_pivot_y,
            "atlas_hint": defaults.atlas_hint,
        },
        "unity": {
            "import_profile_id": profile.unity.import_profile_id,
            "suggested_output_directory": profile.unity.suggested_output_directory,
            "create_material": profile.unity.create_material,
            "pixels_per_unit": profile.unity.pixels_per_unit,
            "pivot_mode": profile.unity.pivot_mode,
            "custom_pivot_x": profile.unity.custom_pivot_x,
            "custom_pivot_y": profile.unity.custom_pivot_y,
            "atlas_hint": profile.unity.atlas_hint,
        },
    }


def dumps_generation_profile(profile: GenerationProfile) -> str:
    """Serialize with stable key ordering, indentation, and trailing newline."""
    return (
        json.dumps(
            generation_profile_to_dict(profile), sort_keys=True, indent=2, ensure_ascii=False
        )
        + "\n"
    )


dumps = dumps_generation_profile
