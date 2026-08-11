"""Structured logging setup."""

from __future__ import annotations

import logging
import sys

# Chrome DevTools Protocol discovery probes (Cursor/IDE/browser tooling often
# scans localhost ports with GET /json/version). Harmless; not part of this API.
_CDP_PROBE_PATHS = (
    "/json",
    "/json/version",
    "/json/list",
    "/json/protocol",
)


class _CdpProbeAccessFilter(logging.Filter):
    """Drop uvicorn access lines for known CDP discovery probes."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        for path in _CDP_PROBE_PATHS:
            # uvicorn: '127.0.0.1:12345 - "GET /json/version HTTP/1.1" 404'
            if f'"GET {path} ' in message or f'"HEAD {path} ' in message:
                return False
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for the application."""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level.upper())
        _install_access_filters()
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())
    _install_access_filters()


def _install_access_filters() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _CdpProbeAccessFilter) for f in access.filters):
        access.addFilter(_CdpProbeAccessFilter())


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
