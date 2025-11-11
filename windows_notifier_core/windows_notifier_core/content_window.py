"""
Content window placeholder for rendering module media.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from shared.module_definition import ModuleDefinition
from .media_viewer import MediaViewerFactory


@dataclass
class ContentWindow(QWidget):
    """Wraps the MediaViewer widget in a top-level window."""

    module: ModuleDefinition = ModuleDefinition.create_placeholder()
    media_factory: MediaViewerFactory = MediaViewerFactory()

    def load_content(self) -> None:
        """Placeholder for instantiating and laying out the viewer."""
        # TODO: create viewer widget and embed it inside the window layout.

    def open(self) -> None:
        """Display the content window."""
        self.show()
