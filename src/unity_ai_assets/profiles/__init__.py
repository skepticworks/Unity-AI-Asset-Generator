"""Public Python profiles API."""

from unity_ai_assets.profiles.compatibility import (
    evaluate_profile_compatibility,
    evaluate_resolved_settings,
)
from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.loader import (
    BuiltinCatalog,
    load_builtin_catalog,
    load_json_file,
    parse_generation_profile,
    parse_negative_prompt_profile,
    parse_prompt_template,
)
from unity_ai_assets.profiles.migration import migrate_profile_payload
from unity_ai_assets.profiles.models import (
    AssetTypeDefinition,
    CompatibilityIssue,
    CompatibilityResult,
    GenerationDefaults,
    GenerationProfile,
    GenerationProfileUnitySettings,
    MigrationResult,
    NegativePromptProfile,
    ProfileProvenance,
    PromptTemplate,
    ResolvedGenerationSettings,
    UnityImportProfileDefinition,
    ValidationIssue,
)
from unity_ai_assets.profiles.negative_prompt_resolver import resolve_negative_prompt
from unity_ai_assets.profiles.prompt_resolver import extract_placeholders, resolve_prompt
from unity_ai_assets.profiles.registry import ProfileRegistry, load_builtin_registry
from unity_ai_assets.profiles.resolver import resolve_generation_profile
from unity_ai_assets.profiles.serialize import (
    dumps_generation_profile,
    generation_profile_to_dict,
)

__all__ = [
    "AssetTypeDefinition",
    "BuiltinCatalog",
    "CompatibilityIssue",
    "CompatibilityResult",
    "GenerationDefaults",
    "GenerationProfile",
    "GenerationProfileUnitySettings",
    "MigrationResult",
    "NegativePromptProfile",
    "ProfileError",
    "ProfileProvenance",
    "ProfileRegistry",
    "PromptTemplate",
    "ResolvedGenerationSettings",
    "UnityImportProfileDefinition",
    "ValidationIssue",
    "dumps_generation_profile",
    "evaluate_profile_compatibility",
    "evaluate_resolved_settings",
    "extract_placeholders",
    "generation_profile_to_dict",
    "load_builtin_catalog",
    "load_builtin_registry",
    "load_json_file",
    "migrate_profile_payload",
    "parse_generation_profile",
    "parse_negative_prompt_profile",
    "parse_prompt_template",
    "resolve_generation_profile",
    "resolve_negative_prompt",
    "resolve_prompt",
]
