"""Stable public API and field-level error codes.

Codes use uppercase snake case and must remain stable even when human-readable
messages change. Clients must key behavior off these codes, not messages.
"""

from __future__ import annotations

from enum import StrEnum


class AppErrorCode(StrEnum):
    """Top-level application error codes returned in the public error envelope."""

    REQUEST_BODY_INVALID = "REQUEST_BODY_INVALID"
    GENERATION_REQUEST_INVALID = "GENERATION_REQUEST_INVALID"
    OPERATION_UNSUPPORTED = "OPERATION_UNSUPPORTED"
    ASSET_TYPE_UNSUPPORTED = "ASSET_TYPE_UNSUPPORTED"
    SCHEDULER_UNSUPPORTED = "SCHEDULER_UNSUPPORTED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_LOADING_FAILED = "MODEL_LOADING_FAILED"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    OUTPUT_PERSISTENCE_FAILED = "OUTPUT_PERSISTENCE_FAILED"
    GENERATION_NOT_FOUND = "GENERATION_NOT_FOUND"
    MANIFEST_NOT_FOUND = "MANIFEST_NOT_FOUND"
    CAPABILITY_SCHEMA_UNSUPPORTED = "CAPABILITY_SCHEMA_UNSUPPORTED"
    MANIFEST_SCHEMA_UNSUPPORTED = "MANIFEST_SCHEMA_UNSUPPORTED"
    TRANSPARENCY_STRATEGY_UNSUPPORTED = "TRANSPARENCY_STRATEGY_UNSUPPORTED"
    BACKGROUND_REMOVAL_UNAVAILABLE = "BACKGROUND_REMOVAL_UNAVAILABLE"
    BACKGROUND_REMOVAL_FAILED = "BACKGROUND_REMOVAL_FAILED"
    SEAM_INPAINT_UNAVAILABLE = "SEAM_INPAINT_UNAVAILABLE"
    SEAM_INPAINT_FAILED = "SEAM_INPAINT_FAILED"
    ALPHA_PROCESSING_FAILED = "ALPHA_PROCESSING_FAILED"
    SPRITE_IMPORT_FAILED = "SPRITE_IMPORT_FAILED"
    PIVOT_INVALID = "PIVOT_INVALID"
    PIXELS_PER_UNIT_INVALID = "PIXELS_PER_UNIT_INVALID"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_STATE_CONFLICT = "JOB_STATE_CONFLICT"
    JOB_NOT_RETRYABLE = "JOB_NOT_RETRYABLE"
    JOB_NOT_CANCELLABLE = "JOB_NOT_CANCELLABLE"
    JOB_CANCELLED = "JOB_CANCELLED"
    JOB_INTERRUPTED = "JOB_INTERRUPTED"
    JOB_SERVICE_UNAVAILABLE = "JOB_SERVICE_UNAVAILABLE"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


class FieldIssueCode(StrEnum):
    """Field-level validation issue codes nested under error details."""

    FIELD_REQUIRED = "FIELD_REQUIRED"
    VALUE_TOO_SHORT = "VALUE_TOO_SHORT"
    VALUE_TOO_LONG = "VALUE_TOO_LONG"
    VALUE_BELOW_MINIMUM = "VALUE_BELOW_MINIMUM"
    VALUE_ABOVE_MAXIMUM = "VALUE_ABOVE_MAXIMUM"
    VALUE_NOT_MULTIPLE = "VALUE_NOT_MULTIPLE"
    VALUE_INVALID = "VALUE_INVALID"
    FORMAT_INVALID = "FORMAT_INVALID"


# Default human-readable messages for top-level codes (safe to change).
DEFAULT_MESSAGES: dict[AppErrorCode, str] = {
    AppErrorCode.REQUEST_BODY_INVALID: "The request body is invalid.",
    AppErrorCode.GENERATION_REQUEST_INVALID: "The generation request is invalid.",
    AppErrorCode.OPERATION_UNSUPPORTED: "The requested operation is not supported.",
    AppErrorCode.ASSET_TYPE_UNSUPPORTED: "The requested asset type is not supported.",
    AppErrorCode.SCHEDULER_UNSUPPORTED: "The requested scheduler is not supported.",
    AppErrorCode.MODEL_UNAVAILABLE: "The configured model is unavailable.",
    AppErrorCode.MODEL_LOADING_FAILED: "The inference model failed to load.",
    AppErrorCode.INFERENCE_FAILED: "Image generation failed.",
    AppErrorCode.OUTPUT_PERSISTENCE_FAILED: "Failed to persist generation outputs.",
    AppErrorCode.GENERATION_NOT_FOUND: "The requested generation was not found.",
    AppErrorCode.MANIFEST_NOT_FOUND: "The generation manifest was not found.",
    AppErrorCode.CAPABILITY_SCHEMA_UNSUPPORTED: "The capability schema version is unsupported.",
    AppErrorCode.MANIFEST_SCHEMA_UNSUPPORTED: (
        "The generation manifest schema version is unsupported."
    ),
    AppErrorCode.TRANSPARENCY_STRATEGY_UNSUPPORTED: (
        "The requested transparency strategy is not supported."
    ),
    AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE: (
        "Background removal is unavailable on this backend."
    ),
    AppErrorCode.BACKGROUND_REMOVAL_FAILED: "Background removal failed.",
    AppErrorCode.SEAM_INPAINT_UNAVAILABLE: (
        "Local seam inpainting is unavailable on this backend."
    ),
    AppErrorCode.SEAM_INPAINT_FAILED: "Local seam inpainting failed.",
    AppErrorCode.ALPHA_PROCESSING_FAILED: "Alpha cleanup processing failed.",
    AppErrorCode.SPRITE_IMPORT_FAILED: "Sprite import failed.",
    AppErrorCode.PIVOT_INVALID: "The requested sprite pivot is invalid.",
    AppErrorCode.PIXELS_PER_UNIT_INVALID: "The requested pixels-per-unit value is invalid.",
    AppErrorCode.JOB_NOT_FOUND: "The requested generation job was not found.",
    AppErrorCode.JOB_STATE_CONFLICT: "The job cannot transition to the requested state.",
    AppErrorCode.JOB_NOT_RETRYABLE: "The job is not eligible for retry.",
    AppErrorCode.JOB_NOT_CANCELLABLE: "The job cannot be cancelled in its current state.",
    AppErrorCode.JOB_CANCELLED: "The generation job was cancelled.",
    AppErrorCode.JOB_INTERRUPTED: "The generation job was interrupted by a backend restart.",
    AppErrorCode.JOB_SERVICE_UNAVAILABLE: "The job service is not accepting new work.",
    AppErrorCode.INTERNAL_SERVER_ERROR: "An unexpected server error occurred.",
}


# HTTP status mapping for application error codes.
HTTP_STATUS_BY_CODE: dict[AppErrorCode, int] = {
    AppErrorCode.REQUEST_BODY_INVALID: 422,
    AppErrorCode.GENERATION_REQUEST_INVALID: 422,
    AppErrorCode.OPERATION_UNSUPPORTED: 422,
    AppErrorCode.ASSET_TYPE_UNSUPPORTED: 422,
    AppErrorCode.SCHEDULER_UNSUPPORTED: 422,
    AppErrorCode.MODEL_UNAVAILABLE: 503,
    AppErrorCode.MODEL_LOADING_FAILED: 503,
    AppErrorCode.INFERENCE_FAILED: 500,
    AppErrorCode.OUTPUT_PERSISTENCE_FAILED: 500,
    AppErrorCode.GENERATION_NOT_FOUND: 404,
    AppErrorCode.MANIFEST_NOT_FOUND: 404,
    AppErrorCode.CAPABILITY_SCHEMA_UNSUPPORTED: 409,
    AppErrorCode.MANIFEST_SCHEMA_UNSUPPORTED: 409,
    AppErrorCode.TRANSPARENCY_STRATEGY_UNSUPPORTED: 422,
    AppErrorCode.BACKGROUND_REMOVAL_UNAVAILABLE: 422,
    AppErrorCode.BACKGROUND_REMOVAL_FAILED: 500,
    AppErrorCode.SEAM_INPAINT_UNAVAILABLE: 422,
    AppErrorCode.SEAM_INPAINT_FAILED: 500,
    AppErrorCode.ALPHA_PROCESSING_FAILED: 500,
    AppErrorCode.SPRITE_IMPORT_FAILED: 500,
    AppErrorCode.PIVOT_INVALID: 422,
    AppErrorCode.PIXELS_PER_UNIT_INVALID: 422,
    AppErrorCode.JOB_NOT_FOUND: 404,
    AppErrorCode.JOB_STATE_CONFLICT: 409,
    AppErrorCode.JOB_NOT_RETRYABLE: 409,
    AppErrorCode.JOB_NOT_CANCELLABLE: 409,
    AppErrorCode.JOB_CANCELLED: 409,
    AppErrorCode.JOB_INTERRUPTED: 500,
    AppErrorCode.JOB_SERVICE_UNAVAILABLE: 503,
    AppErrorCode.INTERNAL_SERVER_ERROR: 500,
}
