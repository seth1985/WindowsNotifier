"""
Media rendering utilities.

Responsible for instantiating the appropriate widget for the media
asset referenced by a module. Implementation will use PySide6 widgets,
WebEngine, or PyMuPDF at a later stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget

from shared.module_definition import ModuleDefinition


class MediaViewerFactory:
    """Factory for creating content widgets based on media type."""

    def create_viewer(self, module: ModuleDefinition) -> Optional[QWidget]:
        """
        Return a widget configured to display the module's media.

        For now, returns None as a placeholder.
        """
        # TODO: inspect module.media_type and produce widget accordingly.
        return None
