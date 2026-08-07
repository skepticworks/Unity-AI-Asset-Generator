"""Resolve generation profiles into concrete request settings."""

from __future__ import annotations

from unity_ai_assets.profiles.compatibility import evaluate_resolved_settings
from unity_ai_assets.profiles.models import (
    GenerationProfile,
    NegativePromptProfile,
    ProfileProvenance,
    PromptTemplate,
    ResolvedGenerationSettings,
)
from unity_ai_assets.profiles.negative_prompt_resolver import resolve_negative_prompt
from unity_ai_assets.profiles.prompt_resolver import resolve_prompt


def resolve_generation_profile(
    profile: GenerationProfile,
    template: PromptTemplate,
    negative_profile: NegativePromptProfile,
    *,
    subject: str,
    additional_prompt: str = "",
    additional_negative: str = "",
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    guidance_scale: float | None = None,
    seed: int | None = None,
    max_prompt_length: int = 2**31 - 1,
    max_negative_prompt_length: int = 2**31 - 1,
) -> ResolvedGenerationSettings:
    """Apply profile defaults then overrides, retaining unsupported values."""
    defaults = profile.generation_defaults
    prompt = resolve_prompt(
        template,
        subject=subject,
        style_modifiers=profile.default_modifiers,
        asset_type=profile.asset_type,
        additional_prompt=additional_prompt,
    )
    negative = resolve_negative_prompt(
        negative_profile,
        additional_terms=profile.additional_negative_terms,
        user_additions=additional_negative,
    )
    provenance = ProfileProvenance(
        generation_profile_id=profile.id,
        generation_profile_revision=profile.revision,
        profile_origin="builtin" if profile.builtin else "user",
        prompt_template_id=template.id,
        prompt_template_revision=template.revision,
        negative_prompt_profile_id=negative_profile.id,
        negative_prompt_profile_revision=negative_profile.revision,
        unity_import_profile_id=profile.unity.import_profile_id,
    )
    resolved = ResolvedGenerationSettings(
        prompt=prompt,
        negative_prompt=negative,
        width=defaults.width if width is None else width,
        height=defaults.height if height is None else height,
        steps=defaults.steps if steps is None else steps,
        guidance_scale=defaults.guidance_scale if guidance_scale is None else guidance_scale,
        seed=defaults.fixed_seed if seed is None else seed,
        asset_type=profile.asset_type,
        unity_import_profile_id=profile.unity.import_profile_id,
        suggested_output_directory=profile.unity.suggested_output_directory,
        create_material=profile.unity.create_material,
        provenance=provenance,
    )
    compatibility = evaluate_resolved_settings(
        resolved,
        supported_asset_types=(profile.asset_type,),
        negative_prompt_supported=True,
        maximum_prompt_length=max_prompt_length,
        maximum_negative_prompt_length=max_negative_prompt_length,
    )
    return ResolvedGenerationSettings(
        prompt=resolved.prompt,
        negative_prompt=resolved.negative_prompt,
        width=resolved.width,
        height=resolved.height,
        steps=resolved.steps,
        guidance_scale=resolved.guidance_scale,
        seed=resolved.seed,
        asset_type=resolved.asset_type,
        unity_import_profile_id=resolved.unity_import_profile_id,
        suggested_output_directory=resolved.suggested_output_directory,
        create_material=resolved.create_material,
        provenance=resolved.provenance,
        compatibility=compatibility,
    )
