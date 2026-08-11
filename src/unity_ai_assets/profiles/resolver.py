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
    transparency_strategy: str | None = None,
    alpha_threshold: int | None = None,
    alpha_feather: int | None = None,
    remove_near_transparent: bool | None = None,
    zero_rgb_when_transparent: bool | None = None,
    pixels_per_unit: float | None = None,
    pivot_mode: str | None = None,
    custom_pivot_x: float | None = None,
    custom_pivot_y: float | None = None,
    atlas_hint: str | None = None,
    tileable: bool | None = None,
    apply_seam_correction: bool | None = None,
    seam_blend_width: int | None = None,
    palette_reduction_enabled: bool | None = None,
    palette_color_count: int | None = None,
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

    resolved_ppu = (
        pixels_per_unit
        if pixels_per_unit is not None
        else (
            profile.unity.pixels_per_unit
            if profile.unity.pixels_per_unit is not None
            else defaults.pixels_per_unit
        )
    )
    resolved_pivot = (
        pivot_mode
        if pivot_mode is not None
        else (
            profile.unity.pivot_mode
            if profile.unity.pivot_mode is not None
            else defaults.pivot_mode
        )
    )
    resolved_pivot_x = (
        custom_pivot_x
        if custom_pivot_x is not None
        else (
            profile.unity.custom_pivot_x
            if profile.unity.custom_pivot_x is not None
            else defaults.custom_pivot_x
        )
    )
    resolved_pivot_y = (
        custom_pivot_y
        if custom_pivot_y is not None
        else (
            profile.unity.custom_pivot_y
            if profile.unity.custom_pivot_y is not None
            else defaults.custom_pivot_y
        )
    )
    resolved_atlas = (
        atlas_hint
        if atlas_hint is not None
        else (
            profile.unity.atlas_hint
            if profile.unity.atlas_hint is not None
            else defaults.atlas_hint
        )
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
        transparency_strategy=(
            defaults.transparency_strategy
            if transparency_strategy is None
            else transparency_strategy
        ),
        alpha_threshold=defaults.alpha_threshold if alpha_threshold is None else alpha_threshold,
        alpha_feather=defaults.alpha_feather if alpha_feather is None else alpha_feather,
        remove_near_transparent=(
            defaults.remove_near_transparent
            if remove_near_transparent is None
            else remove_near_transparent
        ),
        zero_rgb_when_transparent=(
            defaults.zero_rgb_when_transparent
            if zero_rgb_when_transparent is None
            else zero_rgb_when_transparent
        ),
        pixels_per_unit=resolved_ppu,
        pivot_mode=resolved_pivot,
        custom_pivot_x=resolved_pivot_x,
        custom_pivot_y=resolved_pivot_y,
        atlas_hint=resolved_atlas,
        tileable=defaults.tileable if tileable is None else tileable,
        apply_seam_correction=(
            defaults.apply_seam_correction
            if apply_seam_correction is None
            else apply_seam_correction
        ),
        seam_blend_width=(
            defaults.seam_blend_width if seam_blend_width is None else seam_blend_width
        ),
        palette_reduction_enabled=(
            defaults.palette_reduction_enabled
            if palette_reduction_enabled is None
            else palette_reduction_enabled
        ),
        palette_color_count=(
            defaults.palette_color_count if palette_color_count is None else palette_color_count
        ),
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
        transparency_strategy=resolved.transparency_strategy,
        alpha_threshold=resolved.alpha_threshold,
        alpha_feather=resolved.alpha_feather,
        remove_near_transparent=resolved.remove_near_transparent,
        zero_rgb_when_transparent=resolved.zero_rgb_when_transparent,
        pixels_per_unit=resolved.pixels_per_unit,
        pivot_mode=resolved.pivot_mode,
        custom_pivot_x=resolved.custom_pivot_x,
        custom_pivot_y=resolved.custom_pivot_y,
        atlas_hint=resolved.atlas_hint,
        tileable=resolved.tileable,
        apply_seam_correction=resolved.apply_seam_correction,
        seam_blend_width=resolved.seam_blend_width,
        palette_reduction_enabled=resolved.palette_reduction_enabled,
        palette_color_count=resolved.palette_color_count,
        compatibility=compatibility,
    )
