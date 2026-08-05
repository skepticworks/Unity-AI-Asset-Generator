"""Application-specific exceptions."""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected application failures."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class InvalidGenerationParametersError(AppError):
    """Raised when generation request parameters fail validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_parameters")


class ModelLoadError(AppError):
    """Raised when the inference model cannot be loaded or initialized."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="model_load_failed")


class InferenceError(AppError):
    """Raised when image generation fails after the model is loaded."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="inference_failed")


class OutputPersistenceError(AppError):
    """Raised when generated assets cannot be written to disk."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="output_persistence_failed")
