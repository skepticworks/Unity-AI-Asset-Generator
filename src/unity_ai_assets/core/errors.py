"""Application-specific exceptions with stable public error codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from unity_ai_assets.core.error_codes import (
    DEFAULT_MESSAGES,
    AppErrorCode,
    FieldIssueCode,
)


@dataclass(frozen=True, slots=True)
class FieldIssue:
    """A single field-level validation problem with a stable issue code."""

    code: FieldIssueCode
    message: str
    actual: Any | None = None
    minimum: Any | None = None
    maximum: Any | None = None
    expected_multiple: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the public error envelope details.fields map."""
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.actual is not None:
            payload["actual"] = self.actual
        if self.minimum is not None:
            payload["minimum"] = self.minimum
        if self.maximum is not None:
            payload["maximum"] = self.maximum
        if self.expected_multiple is not None:
            payload["expected_multiple"] = self.expected_multiple
        return payload


class AppError(Exception):
    """Base class for expected application failures."""

    def __init__(
        self,
        message: str | None = None,
        *,
        code: AppErrorCode,
        details: dict[str, Any] | None = None,
        field_issues: dict[str, list[FieldIssue]] | None = None,
    ) -> None:
        resolved = message or DEFAULT_MESSAGES.get(code, "An application error occurred.")
        super().__init__(resolved)
        self.message = resolved
        self.code = code
        self.details = details or {}
        self.field_issues = field_issues or {}

    def details_payload(self) -> dict[str, Any] | None:
        """Build optional structured details including field issues."""
        payload = dict(self.details)
        if self.field_issues:
            payload["fields"] = {
                name: [issue.to_dict() for issue in issues]
                for name, issues in self.field_issues.items()
            }
        return payload or None


class GenerationRequestInvalidError(AppError):
    """Raised when generation request parameters fail authoritative validation."""

    def __init__(
        self,
        message: str | None = None,
        *,
        field_issues: dict[str, list[FieldIssue]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=AppErrorCode.GENERATION_REQUEST_INVALID,
            details=details,
            field_issues=field_issues,
        )


# Backward-compatible alias used by older call sites / tests during migration.
InvalidGenerationParametersError = GenerationRequestInvalidError


class ModelLoadError(AppError):
    """Raised when the inference model cannot be loaded or initialized."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.MODEL_LOADING_FAILED)


class ModelUnavailableError(AppError):
    """Raised when the configured model is not available for inference."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.MODEL_UNAVAILABLE)


class InferenceError(AppError):
    """Raised when image generation fails after the model is loaded."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.INFERENCE_FAILED)


class OutputPersistenceError(AppError):
    """Raised when generated assets cannot be written to disk."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.OUTPUT_PERSISTENCE_FAILED)


class GenerationNotFoundError(AppError):
    """Raised when a generation ID does not resolve to stored assets."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.GENERATION_NOT_FOUND)


class ManifestNotFoundError(AppError):
    """Raised when a generation directory exists but the manifest is missing."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.MANIFEST_NOT_FOUND)


class ManifestSchemaUnsupportedError(AppError):
    """Raised when a stored manifest uses an unsupported schema version."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.MANIFEST_SCHEMA_UNSUPPORTED)


class OperationUnsupportedError(AppError):
    """Raised when a requested generation operation is not supported."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.OPERATION_UNSUPPORTED)


class AssetTypeUnsupportedError(AppError):
    """Raised when a requested asset type is not supported."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.ASSET_TYPE_UNSUPPORTED)


class SchedulerUnsupportedError(AppError):
    """Raised when a requested scheduler identifier is not supported."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, code=AppErrorCode.SCHEDULER_UNSUPPORTED)


@dataclass
class ErrorEnvelope:
    """Public API error envelope builder helpers."""

    code: AppErrorCode
    message: str
    request_id: str
    details: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "request_id": self.request_id,
        }
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}
