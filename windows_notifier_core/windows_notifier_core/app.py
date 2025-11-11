"""
High-level application controller for the notifier core.

The concrete business logic will be implemented later. For now we
capture the collaborators required to fulfill the specification and
define placeholder methods that future work can fill in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from PySide6.QtCore import QObject

from . import logger
from .module_loader import ModuleLoader
from .notification_popup import NotificationPopup


@dataclass
class CoreApp(QObject):
    """
    Coordinates module loading, notification display, and the life-cycle
    of the user interactions.
    """

    loader: ModuleLoader = field(default_factory=ModuleLoader)
    active_popups: List[NotificationPopup] = field(default_factory=list)

    def start(self) -> None:
        """Start observing modules and displaying notifications."""
        logger.get_logger().info("CoreApp startup placeholder")
        # TODO: wire up module scanning, idle monitor, and popup handling.

    def shutdown(self) -> None:
        """Placeholder for future teardown logic."""
        logger.get_logger().info("CoreApp shutdown placeholder")
        # TODO: close windows, flush state, etc.
