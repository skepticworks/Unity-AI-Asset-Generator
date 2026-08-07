"""Builtin profile registry, lookup, filtering, and reference validation."""

from __future__ import annotations

import os
from pathlib import Path

from unity_ai_assets.profiles.constants import ProfileErrorCode
from unity_ai_assets.profiles.errors import ProfileError
from unity_ai_assets.profiles.loader import BuiltinCatalog, load_builtin_catalog
from unity_ai_assets.profiles.models import (
    GenerationProfile,
    NegativePromptProfile,
    PromptTemplate,
    UnityImportProfileDefinition,
)


def default_builtin_root() -> Path:
    override = os.environ.get("UNITY_AI_PROFILES_ROOT")
    if override:
        path = Path(override).expanduser()
        return path / "builtin" if (path / "builtin").is_dir() else path
    return Path(__file__).resolve().parents[3] / "profiles" / "builtin"


class ProfileRegistry:
    """Read-only registry of validated canonical builtin profiles."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_builtin_root()).resolve()
        self.catalog: BuiltinCatalog = load_builtin_catalog(self.root)
        self.validate_references()

    @property
    def generation_profiles(self) -> dict[str, GenerationProfile]:
        return self.catalog.generation_profiles

    @property
    def prompt_templates(self) -> dict[str, PromptTemplate]:
        return self.catalog.prompt_templates

    @property
    def negative_prompt_profiles(self) -> dict[str, NegativePromptProfile]:
        return self.catalog.negative_prompt_profiles

    @property
    def import_profiles(self) -> dict[str, UnityImportProfileDefinition]:
        return self.catalog.import_profiles

    def get_generation_profile(self, profile_id: str) -> GenerationProfile:
        try:
            return self.catalog.generation_profiles[profile_id]
        except KeyError as exc:
            raise ProfileError(
                ProfileErrorCode.PROFILE_NOT_FOUND,
                f"Generation profile '{profile_id}' was not found.",
            ) from exc

    def get_prompt_template(self, template_id: str) -> PromptTemplate:
        try:
            return self.catalog.prompt_templates[template_id]
        except KeyError as exc:
            raise ProfileError(
                ProfileErrorCode.PROFILE_TEMPLATE_NOT_FOUND,
                f"Prompt template '{template_id}' was not found.",
            ) from exc

    def get_negative_prompt_profile(self, profile_id: str) -> NegativePromptProfile:
        try:
            return self.catalog.negative_prompt_profiles[profile_id]
        except KeyError as exc:
            raise ProfileError(
                ProfileErrorCode.PROFILE_NEGATIVE_PROFILE_NOT_FOUND,
                f"Negative prompt profile '{profile_id}' was not found.",
            ) from exc

    def get_import_profile(self, profile_id: str) -> UnityImportProfileDefinition:
        try:
            return self.catalog.import_profiles[profile_id]
        except KeyError as exc:
            raise ProfileError(
                ProfileErrorCode.PROFILE_IMPORT_PROFILE_NOT_FOUND,
                f"Unity import profile '{profile_id}' was not found.",
            ) from exc

    def filter_by_asset_type(self, asset_type: str) -> tuple[GenerationProfile, ...]:
        return tuple(
            profile
            for _, profile in sorted(self.catalog.generation_profiles.items())
            if profile.asset_type == asset_type
        )

    def validate_references(self) -> None:
        for profile in self.catalog.generation_profiles.values():
            template = self.catalog.prompt_templates.get(profile.template_id)
            negative = self.catalog.negative_prompt_profiles.get(profile.negative_prompt_profile_id)
            imported = self.catalog.import_profiles.get(profile.unity.import_profile_id)
            if template is None or template.revision != profile.template_revision:
                self._invalid(profile.id, "prompt template", profile.template_id)
            if negative is None or negative.revision != profile.negative_prompt_profile_revision:
                self._invalid(
                    profile.id, "negative prompt profile", profile.negative_prompt_profile_id
                )
            if imported is None or profile.asset_type not in imported.asset_types:
                self._invalid(profile.id, "Unity import profile", profile.unity.import_profile_id)
            if template is not None and template.asset_type != profile.asset_type:
                self._invalid(profile.id, "asset type", template.asset_type)
        for asset_type in self.catalog.asset_types.values():
            if asset_type.default_generation_profile_id not in self.catalog.generation_profiles:
                self._invalid(
                    asset_type.id,
                    "default generation profile",
                    asset_type.default_generation_profile_id,
                )
            if asset_type.default_import_profile_id not in self.catalog.import_profiles:
                self._invalid(
                    asset_type.id, "default import profile", asset_type.default_import_profile_id
                )

    @staticmethod
    def _invalid(owner: str, category: str, value: str) -> None:
        raise ProfileError(
            ProfileErrorCode.PROFILE_REFERENCE_INVALID,
            f"'{owner}' references invalid {category} '{value}'.",
        )


def load_builtin_registry(root: Path | None = None) -> ProfileRegistry:
    return ProfileRegistry(root)
