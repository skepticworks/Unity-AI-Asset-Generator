"""Central public version constants for the API and schemas.

Application semantic version is resolved from installed package metadata when
available, otherwise from the controlled fallback below. Schema versions are
independent of the application version.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

# --- Public API versioning (independent of application semver) ---
API_MAJOR_VERSION: int = 1
API_MINOR_VERSION: int = 4

# --- Schema versions (explicit; do not infer from application version) ---
CAPABILITIES_SCHEMA_VERSION: str = "1.6"
JOB_RECORD_SCHEMA_VERSION: str = "1.1"
BATCH_RECORD_SCHEMA_VERSION: str = "1.0"
GENERATION_MANIFEST_SCHEMA_VERSION: str = "1.5"
GENERATION_MANIFEST_SCHEMA_NAME: str = "generation-manifest"
GENERATION_PROFILE_SCHEMA_NAME: str = "generation-profile"
GENERATION_PROFILE_SCHEMA_VERSION: str = "1.2"
PROMPT_TEMPLATE_SCHEMA_NAME: str = "prompt-template"
PROMPT_TEMPLATE_SCHEMA_VERSION: str = "1.0"
NEGATIVE_PROMPT_PROFILE_SCHEMA_NAME: str = "negative-prompt-profile"
NEGATIVE_PROMPT_PROFILE_SCHEMA_VERSION: str = "1.0"
ASSET_TYPE_CATALOG_SCHEMA_NAME: str = "asset-type-catalog"
ASSET_TYPE_CATALOG_SCHEMA_VERSION: str = "1.0"
UNITY_IMPORT_PROFILE_CATALOG_SCHEMA_NAME: str = "unity-import-profile-catalog"
UNITY_IMPORT_PROFILE_CATALOG_SCHEMA_VERSION: str = "1.0"

# --- Application identity ---
APPLICATION_NAME: str = "unity-ai-asset-generator"
APPLICATION_VERSION_FALLBACK: str = "0.10.0"
PACKAGE_DISTRIBUTION_NAME: str = "unity-ai-assets"


def resolve_application_version() -> str:
    """Return the installed package version, or the documented fallback."""
    try:
        return package_version(PACKAGE_DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return APPLICATION_VERSION_FALLBACK


APPLICATION_VERSION: str = resolve_application_version()
