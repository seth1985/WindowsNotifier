"""
Logging setup for the notifier core.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _logger

_LOG_INITIALISED = False
LOG_DIR = Path.home() / "AppData" / "Local" / "Windows Notifier" / "Core"
DEFAULT_LOG_PATH = LOG_DIR / "core.log"


def configure(log_path: Optional[Path] = None) -> None:
    """
    Configure loguru for the application.

    Delays actual configuration for the future implementation; currently
    ensures configuration occurs only once.
    """
    global _LOG_INITIALISED
    if _LOG_INITIALISED:
        return
    target = log_path or DEFAULT_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    # Keep console output and add a persistent file sink.
    _logger.remove()
    if sys.stderr is not None:
        _logger.add(sys.stderr, level="INFO", enqueue=True)
    _logger.add(
        target,
        level="DEBUG",
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    _LOG_INITIALISED = True


def get_logger():
    """Return the shared logger instance."""
    configure()
    return _logger
