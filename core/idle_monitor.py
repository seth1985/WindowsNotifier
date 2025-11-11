"""
Idle monitoring using Win32 GetLastInputInfo for "Remind me later" flow.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal


class IdleMonitor(QObject):
    """
    Periodically polls system idle time and emits a signal once the configured
    threshold is exceeded. Monitoring halts after emission until restarted.
    """

    idleReached = Signal()

    def __init__(self, threshold_seconds: int = 600, poll_interval_ms: int = 5000) -> None:
        super().__init__()
        self.threshold_seconds = threshold_seconds
        self._poll_interval_ms = poll_interval_ms
        self._timer = QTimer(self)
        self._timer.setInterval(self._poll_interval_ms)
        self._timer.timeout.connect(self._check_idle)  # type: ignore[arg-type]
        self._active = False
        self._idle_seconds_provider: Optional[Callable[[], float]] = None

    def start(self) -> None:
        """Begin monitoring user idle time."""
        if self._active:
            return
        self._active = True
        self._timer.start()

    def stop(self) -> None:
        """Stop monitoring."""
        if not self._active:
            return
        self._timer.stop()
        self._active = False

    def set_idle_seconds_provider(self, provider: Callable[[], float]) -> None:
        """
        Override idle seconds acquisition. Primarily used for testing.
        """
        self._idle_seconds_provider = provider

    def _check_idle(self) -> None:
        if not self._active:
            return

        try:
            idle_seconds = self._get_idle_seconds()
        except OSError:
            # If querying idle time fails, pause monitoring rather than crashing.
            self.stop()
            return

        if idle_seconds >= self.threshold_seconds:
            self.idleReached.emit()
            self.stop()

    def _get_idle_seconds(self) -> float:
        if self._idle_seconds_provider is not None:
            return self._idle_seconds_provider()

        last_input_info = _get_last_input_info()
        tick_count_ms = _get_tick_count_ms()
        idle_ms = max(0, tick_count_ms - last_input_info)
        return idle_ms / 1000.0


def _get_last_input_info() -> int:
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    last_input = LASTINPUTINFO()
    last_input.cbSize = ctypes.sizeof(LASTINPUTINFO)

    if not user32.GetLastInputInfo(ctypes.byref(last_input)):
        raise ctypes.WinError()

    return last_input.dwTime


def _get_tick_count_ms() -> int:
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    if hasattr(kernel32, "GetTickCount64"):
        return int(kernel32.GetTickCount64())
    return int(kernel32.GetTickCount())
