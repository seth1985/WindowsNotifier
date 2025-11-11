"""
Entry point for the windows_notifier_core application.
"""

from __future__ import annotations

import ctypes
import sys
import time
from typing import Iterable, Tuple

from PySide6.QtWidgets import QApplication

from core.app import AppCoordinator
from windows_notifier_core.windows_notifier_core import logger as app_logger

_LOGGER = app_logger.get_logger()
_MUTEX_NAME = "Global\\WindowsNotifierCoreMutex"
_ERROR_ALREADY_EXISTS = 183


class _InstanceGuard:
    """Simple named mutex guard to prevent concurrent instances."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._handle = None
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None

    def acquire(self) -> bool:
        if self._kernel32 is None:
            return True
        ctypes.set_last_error(0)
        handle = self._kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            # If we cannot create the mutex we silently allow the instance.
            return True
        last_error = ctypes.get_last_error()
        if last_error == _ERROR_ALREADY_EXISTS:
            self._kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._kernel32 is None or not self._handle:
            return
        self._kernel32.ReleaseMutex(self._handle)
        self._kernel32.CloseHandle(self._handle)
        self._handle = None


def _run_application_once(argv: Iterable[str]) -> Tuple[int, bool]:
    """Start the Qt application once and report whether shutdown was intentional."""
    app = QApplication(list(argv))
    coordinator = AppCoordinator()
    coordinator.start()
    exit_code = app.exec()
    manual_shutdown = getattr(coordinator, "manual_shutdown_requested", False)
    return exit_code, bool(manual_shutdown)


def main() -> int:
    """Launch the application with single-instance + recovery safeguards."""
    guard = _InstanceGuard(_MUTEX_NAME)
    if not guard.acquire():
        _LOGGER.debug("Windows Notifier Core instance already running; exiting silently.")
        return 0

    backoff_seconds = 2
    max_backoff = 30

    try:
        while True:
            try:
                exit_code, manual = _run_application_once(sys.argv)
            except Exception:  # pragma: no cover - defensive crash guard
                _LOGGER.exception("Core app crashed; attempting automatic recovery.")
                exit_code = 1
                manual = False

            if manual:
                return exit_code

            _LOGGER.warning(
                "Core app exited unexpectedly (code=%s). Restarting in %s seconds.",
                exit_code,
                backoff_seconds,
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, max_backoff)
    finally:
        guard.release()


if __name__ == "__main__":
    raise SystemExit(main())
