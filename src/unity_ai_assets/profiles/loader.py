"""Bounded JSON loading and typed profile parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from unity_ai_assets.profiles.constants import (
    ASSET_TYPE_CATALOG_SCHEMA_NAME,
    ASSET_TYPE_CATALOG_SCHEMA_VERSION,
    GENERATION_PROFILE_SCHEMA_NAME,
    GENERATION_PROFILE_SCHEMA_VERSION,
    MAX_PROFILE_FILE_SIZE,
    NEGATIVE_PROMPT_PROFILE_SCHEMA_NAME,
    NEGATIVE_PROMPT_PROFILE_SCHEMA_VERSION,
    PROMPT_TEMPLATE_SCHEMA_NAME,
    PROMPT_TEMPLATE_SCHEMA_VERSION,
    UNITY_IMPORT_PROFILE_CATALOG_SCHEMA_NAME,
    UNITY_IMPORT_PROFILE_CATALOG_SCHEMA_VERSION,
    ProfileErrorCode,
)
from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.models import (
    AssetTypeDefinition,
    GenerationDefaults,
    GenerationProfile,
    GenerationProfileUnitySettings,
    NegativePromptProfile,
    PromptTemplate,
    UnityImportProfileDefinition,
)
from unity_ai_assets.profiles.schema_version import is_compatible
from unity_ai_assets.profiles.validation import (
    require_no_secrets,
    require_valid_generation_profile,
    validate_profile_id,
)


@dataclass(frozen=True, slots=True)
class BuiltinCatalog:
    asset_types: dict[str, AssetTypeDefinition]
    import_profiles: dict[str, UnityImportProfileDefinition]
    prompt_templates: dict[str, PromptTemplate]
    negative_prompt_profiles: dict[str, NegativePromptProfile]
    generation_profiles: dict[str, GenerationProfile]


def load_json_file(path: Path) -> dict[str, Any]:
    """Read one bounded UTF-8 JSON object."""
    try:
        if path.stat().st_size > MAX_PROFILE_FILE_SIZE:
            raise ProfileError(
                ProfileErrorCode.PROFILE_SCHEMA_INVALID,
                f"Profile file exceeds {MAX_PROFILE_FILE_SIZE} bytes: {path}.",
            )
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except ProfileError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError(
            ProfileErrorCode.PROFILE_IMPORT_FAILED, f"Could not load profile file '{path}'."
        ) from exc
    if not isinstance(payload, dict):
        raise ProfileError(ProfileErrorCode.PROFILE_SCHEMA_INVALID, "JSON root must be an object.")
    result = cast(dict[str, Any], payload)
    require_no_secrets(result)
    return result


def _object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID, f"Missing object field '{key}'."
        )
    return cast(dict[str, Any], value)


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID, f"Field '{field}' must be an array."
        )
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    items = _list(value, field)
    if not all(isinstance(item, str) for item in items):
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID, f"Field '{field}' must contain strings."
        )
    return tuple(cast(list[str], items))


def _check_schema(payload: dict[str, Any], name: str, version: str) -> str:
    schema = _object(payload, "schema")
    if schema.get("name") != name:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_UNSUPPORTED,
            f"Expected schema '{name}', got '{schema.get('name')}'.",
        )
    declared = schema.get("version")
    if not isinstance(declared, str):
        raise ProfileError(ProfileErrorCode.PROFILE_SCHEMA_INVALID, "Schema version is missing.")
    is_compatible(version, declared)
    return declared


def parse_prompt_template(payload: dict[str, Any]) -> PromptTemplate:
    _check_schema(payload, PROMPT_TEMPLATE_SCHEMA_NAME, PROMPT_TEMPLATE_SCHEMA_VERSION)
    item = _object(payload, "template")
    try:
        template = PromptTemplate(
            id=validate_profile_id(str(item["id"])),
            revision=int(item["revision"]),
            display_name=str(item["display_name"]),
            description=str(item["description"]),
            asset_type=str(item["asset_type"]),
            pattern=str(item["pattern"]),
            placeholders=_strings(item["placeholders"], "placeholders"),
            required_placeholders=_strings(item["required_placeholders"], "required_placeholders"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID, f"Invalid prompt template: {exc}."
        ) from exc
    return template


def parse_negative_prompt_profile(payload: dict[str, Any]) -> NegativePromptProfile:
    _check_schema(
        payload, NEGATIVE_PROMPT_PROFILE_SCHEMA_NAME, NEGATIVE_PROMPT_PROFILE_SCHEMA_VERSION
    )
    item = _object(payload, "profile")
    try:
        return NegativePromptProfile(
            id=validate_profile_id(str(item["id"])),
            revision=int(item["revision"]),
            display_name=str(item["display_name"]),
            description=str(item["description"]),
            tags=_strings(item["tags"], "tags"),
            terms=_strings(item["terms"], "terms"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID, f"Invalid negative prompt profile: {exc}."
        ) from exc


def parse_generation_profile(
    payload: dict[str, Any], *, builtin_default: bool | None = None
) -> GenerationProfile:
    schema_version = _check_schema(
        payload, GENERATION_PROFILE_SCHEMA_NAME, GENERATION_PROFILE_SCHEMA_VERSION
    )
    item = _object(payload, "profile")
    prompt = _object(payload, "prompt")
    negative = _object(payload, "negative_prompt")
    defaults = _object(payload, "generation_defaults")
    unity = _object(payload, "unity")
    try:
        builtin_raw = item.get("builtin", builtin_default if builtin_default is not None else False)
        if not isinstance(builtin_raw, bool):
            raise TypeError("profile.builtin must be a boolean")
        profile = GenerationProfile(
            id=validate_profile_id(str(item["id"])),
            revision=int(item["revision"]),
            display_name=str(item["display_name"]),
            description=str(item["description"]),
            asset_type=str(item["asset_type"]),
            builtin=builtin_raw,
            tags=_strings(item["tags"], "tags"),
            template_id=validate_profile_id(str(prompt["template_id"])),
            template_revision=int(prompt["template_revision"]),
            default_modifiers=_strings(prompt["default_modifiers"], "default_modifiers"),
            negative_prompt_profile_id=validate_profile_id(str(negative["profile_id"])),
            negative_prompt_profile_revision=int(negative["profile_revision"]),
            additional_negative_terms=_strings(negative["additional_terms"], "additional_terms"),
            generation_defaults=GenerationDefaults(
                width=int(defaults["width"]),
                height=int(defaults["height"]),
                steps=int(defaults["steps"]),
                guidance_scale=float(defaults["guidance_scale"]),
                seed_strategy=str(defaults["seed_strategy"]),
                fixed_seed=(
                    None if defaults.get("fixed_seed") is None else int(defaults["fixed_seed"])
                ),
            ),
            unity=GenerationProfileUnitySettings(
                import_profile_id=validate_profile_id(str(unity["import_profile_id"])),
                suggested_output_directory=str(unity["suggested_output_directory"]),
                create_material=bool(unity["create_material"]),
            ),
            schema_version=schema_version,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProfileError(
            ProfileErrorCode.PROFILE_SCHEMA_INVALID, f"Invalid generation profile: {exc}."
        ) from exc
    require_valid_generation_profile(profile)
    return profile


def _insert_unique(registry: dict[str, Any], item: Any, category: str) -> None:
    item_id = str(item.id)
    if item_id in registry:
        raise ProfileError(
            ProfileErrorCode.PROFILE_ID_DUPLICATE,
            f"Duplicate {category} identifier '{item_id}'.",
        )
    registry[item_id] = item


def load_builtin_catalog(root: Path) -> BuiltinCatalog:
    """Load every canonical builtin catalog and profile deterministically."""
    asset_payload = load_json_file(root / "asset_types.json")
    _check_schema(asset_payload, ASSET_TYPE_CATALOG_SCHEMA_NAME, ASSET_TYPE_CATALOG_SCHEMA_VERSION)
    asset_types: dict[str, AssetTypeDefinition] = {}
    for raw in _list(asset_payload.get("asset_types"), "asset_types"):
        if not isinstance(raw, dict):
            raise ProfileError(ProfileErrorCode.PROFILE_SCHEMA_INVALID, "Invalid asset type.")
        item = cast(dict[str, Any], raw)
        definition = AssetTypeDefinition(
            id=validate_profile_id(str(item["id"])),
            display_name=str(item["display_name"]),
            description=str(item["description"]),
            default_generation_profile_id=str(item["default_generation_profile_id"]),
            default_import_profile_id=str(item["default_import_profile_id"]),
            suggested_output_directory=str(item["suggested_output_directory"]),
        )
        _insert_unique(asset_types, definition, "asset type")

    import_payload = load_json_file(root / "import_profiles.json")
    _check_schema(
        import_payload,
        UNITY_IMPORT_PROFILE_CATALOG_SCHEMA_NAME,
        UNITY_IMPORT_PROFILE_CATALOG_SCHEMA_VERSION,
    )
    imports: dict[str, UnityImportProfileDefinition] = {}
    for raw in _list(import_payload.get("import_profiles"), "import_profiles"):
        item = cast(dict[str, Any], raw)
        import_definition = UnityImportProfileDefinition(
            id=validate_profile_id(str(item["id"])),
            display_name=str(item["display_name"]),
            description=str(item["description"]),
            asset_types=_strings(item["asset_types"], "asset_types"),
            legacy_kind=None if item.get("legacy_kind") is None else str(item["legacy_kind"]),
            settings=dict(cast(dict[str, Any], item["settings"])),
        )
        _insert_unique(imports, import_definition, "import profile")

    templates: dict[str, PromptTemplate] = {}
    for path in sorted((root / "prompt_templates").glob("*.json")):
        _insert_unique(templates, parse_prompt_template(load_json_file(path)), "prompt template")
    negatives: dict[str, NegativePromptProfile] = {}
    for path in sorted((root / "negative_prompts").glob("*.json")):
        _insert_unique(
            negatives,
            parse_negative_prompt_profile(load_json_file(path)),
            "negative prompt profile",
        )
    profiles: dict[str, GenerationProfile] = {}
    for path in sorted((root / "generation").glob("*.json")):
        _insert_unique(
            profiles,
            parse_generation_profile(load_json_file(path), builtin_default=True),
            "generation profile",
        )
    return BuiltinCatalog(asset_types, imports, templates, negatives, profiles)
