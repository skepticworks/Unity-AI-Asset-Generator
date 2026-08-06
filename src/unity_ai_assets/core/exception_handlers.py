"""Public exception handlers and error envelope helpers for /api/v1 routes."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from unity_ai_assets.core.error_codes import (
    DEFAULT_MESSAGES,
    HTTP_STATUS_BY_CODE,
    AppErrorCode,
    FieldIssueCode,
)
from unity_ai_assets.core.errors import AppError, ErrorEnvelope
from unity_ai_assets.core.logging import get_logger
from unity_ai_assets.core.request_context import get_request_id

logger = get_logger(__name__)


def _request_id_or_unknown() -> str:
    return get_request_id() or "unknown"


def build_error_response(
    *,
    code: AppErrorCode,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    status_code: int | None = None,
) -> JSONResponse:
    """Build a JSONResponse using the stable public error envelope."""
    envelope = ErrorEnvelope(
        code=code,
        message=message or DEFAULT_MESSAGES[code],
        request_id=_request_id_or_unknown(),
        details=details,
    )
    return JSONResponse(
        status_code=status_code or HTTP_STATUS_BY_CODE[code],
        content=envelope.to_dict(),
    )


def _map_pydantic_type(error_type: str) -> FieldIssueCode:
    mapping: dict[str, FieldIssueCode] = {
        "missing": FieldIssueCode.FIELD_REQUIRED,
        "string_too_short": FieldIssueCode.VALUE_TOO_SHORT,
        "string_too_long": FieldIssueCode.VALUE_TOO_LONG,
        "greater_than_equal": FieldIssueCode.VALUE_BELOW_MINIMUM,
        "greater_than": FieldIssueCode.VALUE_BELOW_MINIMUM,
        "less_than_equal": FieldIssueCode.VALUE_ABOVE_MAXIMUM,
        "less_than": FieldIssueCode.VALUE_ABOVE_MAXIMUM,
        "int_parsing": FieldIssueCode.FORMAT_INVALID,
        "float_parsing": FieldIssueCode.FORMAT_INVALID,
        "bool_parsing": FieldIssueCode.FORMAT_INVALID,
        "json_invalid": FieldIssueCode.FORMAT_INVALID,
        "value_error": FieldIssueCode.VALUE_INVALID,
    }
    return mapping.get(error_type, FieldIssueCode.VALUE_INVALID)


def translate_validation_errors(exc: RequestValidationError) -> dict[str, list[dict[str, Any]]]:
    """Convert FastAPI/Pydantic validation errors into field-level issue maps."""
    fields: dict[str, list[dict[str, Any]]] = {}
    for err in exc.errors():
        loc = err.get("loc", ())
        parts = [str(part) for part in loc if part not in {"body", "query", "path", "header"}]
        field_name = ".".join(parts) if parts else "body"
        issue_code = _map_pydantic_type(str(err.get("type", "")))
        issue: dict[str, Any] = {
            "code": issue_code.value,
            "message": str(err.get("msg", "Invalid value")),
        }
        if "ctx" in err and isinstance(err["ctx"], dict):
            ctx = err["ctx"]
            if "ge" in ctx:
                issue["minimum"] = ctx["ge"]
            if "le" in ctx:
                issue["maximum"] = ctx["le"]
            if "max_length" in ctx:
                issue["maximum"] = ctx["max_length"]
            if "min_length" in ctx:
                issue["minimum"] = ctx["min_length"]
        if "input" in err and err["input"] is not None:
            # Avoid dumping huge bodies into errors.
            raw = err["input"]
            if isinstance(raw, str | int | float | bool) or raw is None:
                issue["actual"] = raw
            elif isinstance(raw, list | dict):
                issue["actual"] = f"<{type(raw).__name__}>"
        fields.setdefault(field_name, []).append(issue)
    return fields


def register_exception_handlers(app: FastAPI) -> None:
    """Attach stable error handlers to the application."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        status = HTTP_STATUS_BY_CODE.get(exc.code, 500)
        logger.error(
            "Application error code=%s request_id=%s message=%s",
            exc.code.value,
            _request_id_or_unknown(),
            exc.message,
        )
        return build_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details_payload(),
            status_code=status,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        fields = translate_validation_errors(exc)
        logger.info(
            "Request validation failed request_id=%s fields=%s",
            _request_id_or_unknown(),
            list(fields.keys()),
        )
        return build_error_response(
            code=AppErrorCode.REQUEST_BODY_INVALID,
            message=DEFAULT_MESSAGES[AppErrorCode.REQUEST_BODY_INVALID],
            details={"fields": fields},
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            code = AppErrorCode.GENERATION_NOT_FOUND
            message = str(exc.detail) if exc.detail else DEFAULT_MESSAGES[code]
            # Only use GENERATION_NOT_FOUND for generation paths; otherwise generic.
            path = _request.url.path if _request else ""
            if "/generations/" not in path:
                code = AppErrorCode.INTERNAL_SERVER_ERROR
                message = "The requested resource was not found."
                return build_error_response(code=code, message=message, status_code=404)
            return build_error_response(code=code, message=message, status_code=404)
        return build_error_response(
            code=AppErrorCode.INTERNAL_SERVER_ERROR,
            message=str(exc.detail)
            if exc.detail
            else DEFAULT_MESSAGES[AppErrorCode.INTERNAL_SERVER_ERROR],
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception request_id=%s type=%s",
            _request_id_or_unknown(),
            type(exc).__name__,
        )
        return build_error_response(
            code=AppErrorCode.INTERNAL_SERVER_ERROR,
            message=DEFAULT_MESSAGES[AppErrorCode.INTERNAL_SERVER_ERROR],
            status_code=500,
        )
