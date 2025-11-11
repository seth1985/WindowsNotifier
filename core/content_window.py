"""
Top-level window responsible for rendering module media content.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget

from shared.module_definition import ModuleDefinition
from core.media_viewer import choose_viewer


class ContentWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Notification Content")
        self._current_widget: QWidget | None = None

    def show_content(self, module: ModuleDefinition) -> None:
        """Render the module's media inside the window."""
        widget = choose_viewer(module)
        self._set_central_widget(widget)
        self.show()

    def _set_central_widget(self, widget: QWidget) -> None:
        if self._current_widget is not None:
            self._current_widget.setParent(None)
        self._current_widget = widget
        self.setCentralWidget(widget)
