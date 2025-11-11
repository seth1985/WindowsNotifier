"""
Overlay window placeholder that presents module actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtWidgets import QWidget

from shared.module_definition import ModuleDefinition


@dataclass
class ModuleOverlay(QWidget):
    """
    Provides the three-button interaction model:
    - Show me how
    - I understand
    - Remind me later
    """

    module: ModuleDefinition = ModuleDefinition.create_placeholder()
    on_show_me_how: Optional[Callable[[ModuleDefinition], None]] = None
    on_i_understand: Optional[Callable[[ModuleDefinition], None]] = None
    on_remind_me_later: Optional[Callable[[ModuleDefinition], None]] = None

    def present(self) -> None:
        """Placeholder to display the overlay."""
        self.show()
