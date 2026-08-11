"""Immutable domain models for profile catalogs and resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from unity_ai_assets.profiles.constants import CompatibilityState


@dataclass(frozen=True, slots=True)
class AssetTypeDefinition:
    id: str
    display_name: str
    description: str
    default_generation_profile_id: str
    default_import_profile_id: str
    suggested_output_directory: str


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    id: str
    revision: int
    display_name: str
    description: str
    asset_type: str
    pattern: str
    placeholders: tuple[str, ...]
    required_placeholders: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NegativePromptProfile:
    id: str
    revision: int
    display_name: str
    description: str
    tags: tuple[str, ...]
    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnityImportProfileDefinition:
    id: str
    display_name: str
    description: str
    asset_types: tuple[str, ...]
    legacy_kind: str | None
    settings: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GenerationDefaults:
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed_strategy: str
    fixed_seed: int | None
    transparency_strategy: str = "none"
    alpha_threshold: int = 16
    alpha_feather: int = 0
    remove_near_transparent: bool = True
    zero_rgb_when_transparent: bool = True
    pixels_per_unit: float | None = None
    pivot_mode: str | None = None
    custom_pivot_x: float | None = None
    custom_pivot_y: float | None = None
    atlas_hint: str | None = None
    tileable: bool = False
    apply_seam_correction: bool = False
    seam_blend_width: int = 8
    palette_reduction_enabled: bool = False
    palette_color_count: int = 16


@dataclass(frozen=True, slots=True)
class GenerationProfileUnitySettings:
    import_profile_id: str
    suggested_output_directory: str
    create_material: bool
    pixels_per_unit: float | None = None
    pivot_mode: str | None = None
    custom_pivot_x: float | None = None
    custom_pivot_y: float | None = None
    atlas_hint: str | None = None


@dataclass(frozen=True, slots=True)
class GenerationProfile:
    id: str
    revision: int
    display_name: str
    description: str
    asset_type: str
    builtin: bool
    tags: tuple[str, ...]
    template_id: str
    template_revision: int
    default_modifiers: tuple[str, ...]
    negative_prompt_profile_id: str
    negative_prompt_profile_revision: int
    additional_negative_terms: tuple[str, ...]
    generation_defaults: GenerationDefaults
    unity: GenerationProfileUnitySettings
    schema_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class ProfileProvenance:
    generation_profile_id: str | None = None
    generation_profile_revision: int | None = None
    profile_origin: str = "none"
    prompt_template_id: str | None = None
    prompt_template_revision: int | None = None
    negative_prompt_profile_id: str | None = None
    negative_prompt_profile_revision: int | None = None
    unity_import_profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompatibilityIssue:
    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    state: CompatibilityState
    issues: tuple[CompatibilityIssue, ...] = ()

    @property
    def compatible(self) -> bool:
        return self.state == CompatibilityState.COMPATIBLE


@dataclass(frozen=True, slots=True)
class ResolvedGenerationSettings:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed: int | None
    asset_type: str
    unity_import_profile_id: str
    suggested_output_directory: str
    create_material: bool
    provenance: ProfileProvenance
    transparency_strategy: str = "none"
    alpha_threshold: int = 16
    alpha_feather: int = 0
    remove_near_transparent: bool = True
    zero_rgb_when_transparent: bool = True
    pixels_per_unit: float | None = None
    pivot_mode: str | None = None
    custom_pivot_x: float | None = None
    custom_pivot_y: float | None = None
    atlas_hint: str | None = None
    tileable: bool = False
    apply_seam_correction: bool = False
    seam_blend_width: int = 8
    palette_reduction_enabled: bool = False
    palette_color_count: int = 16
    compatibility: CompatibilityResult = field(
        default_factory=lambda: CompatibilityResult(CompatibilityState.COMPATIBLE)
    )


@dataclass(frozen=True, slots=True)
class MigrationResult:
    migrated: bool
    source_version: str
    target_version: str
    steps: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    category: Literal["schema", "registry", "compatibility"]
    code: str
    message: str
    field: str | None = None
