"""
Logging utilities for the builder application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger as _logger

_LOG_INITIALISED = False


def configure(log_path: Optional[Path] = None) -> None:
    """Prepare loguru configuration."""
    global _LOG_INITIALISED
    if _LOG_INITIALISED:
        return
    # TODO: configure sinks / formatting suited for the builder.
    _LOG_INITIALISED = True


def get_logger():
    """Return the shared logger instance, configuring on first use."""
    configure()
    return _logger
