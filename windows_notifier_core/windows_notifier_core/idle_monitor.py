"""
System idle monitoring placeholder.

Final implementation will query `GetLastInputInfo` via pywin32 to detect
system idle time and trigger reminders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class IdleMonitor:
    """
    Watches for user idle time and invokes a callback when thresholds are met.
    """

    idle_threshold_minutes: int = 10
    on_idle: Optional[Callable[[], None]] = None

    def start(self) -> None:
        """Begin monitoring; placeholder no-op for now."""
        # TODO: start a timer or background thread invoking GetLastInputInfo.

    def stop(self) -> None:
        """Stop monitoring; placeholder."""
        # TODO: cancel timers/background workers if applicable.
