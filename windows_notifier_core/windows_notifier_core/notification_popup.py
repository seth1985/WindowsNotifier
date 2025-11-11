"""
Notification popup window placeholder.

Defines the structure of the popup displayed in the system tray area.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtWidgets import QWidget

from shared.module_definition import ModuleDefinition


@dataclass
class NotificationPopup(QWidget):
    """
    Frameless window presenting module metadata. The actual UI layout
    and animation will be implemented later.
    """

    module: ModuleDefinition = ModuleDefinition.create_placeholder()
    on_clicked: Optional[Callable[[ModuleDefinition], None]] = None

    def show_popup(self) -> None:
        """Display the popup. Placeholder calls QWidget.show()."""
        self.show()

    def close_popup(self) -> None:
        """Close the popup."""
        self.close()
