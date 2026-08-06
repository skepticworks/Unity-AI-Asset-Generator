"""Unit tests for request ID validation and stable error translation."""

from __future__ import annotations

from fastapi.exceptions import RequestValidationError

from unity_ai_assets.core.error_codes import AppErrorCode, FieldIssueCode
from unity_ai_assets.core.exception_handlers import translate_validation_errors
from unity_ai_assets.core.request_context import (
    generate_request_id,
    is_valid_request_id,
    resolve_request_id,
)


def test_request_id_generation() -> None:
    value = generate_request_id()
    assert is_valid_request_id(value)


def test_request_id_validation() -> None:
    assert is_valid_request_id("abc-123")
    assert not is_valid_request_id("")
    assert not is_valid_request_id("has spaces")
    assert not is_valid_request_id("bad\ninjection")
    assert not is_valid_request_id("x" * 65)


def test_invalid_request_id_replaced() -> None:
    resolved = resolve_request_id("not valid!")
    assert resolved != "not valid!"
    assert is_valid_request_id(resolved)


def test_valid_request_id_preserved() -> None:
    assert resolve_request_id("client-1") == "client-1"


def test_error_code_catalog() -> None:
    assert AppErrorCode.GENERATION_REQUEST_INVALID.value == "GENERATION_REQUEST_INVALID"
    assert FieldIssueCode.VALUE_NOT_MULTIPLE.value == "VALUE_NOT_MULTIPLE"


def test_validation_error_translation() -> None:
    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "prompt"),
                "msg": "Field required",
                "input": {},
            }
        ]
    )
    fields = translate_validation_errors(exc)
    assert "prompt" in fields
    assert fields["prompt"][0]["code"] == FieldIssueCode.FIELD_REQUIRED.value
