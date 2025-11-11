"""
Media selection helpers for the builder UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QFileDialog, QWidget


@dataclass
class MediaPicker:
    """Wraps QFileDialog interaction for selecting media files."""

    def pick_media_file(self, parent: Optional[QWidget] = None) -> Optional[Path]:
        filters = (
            "Media Files (*.pdf *.png *.jpg *.jpeg *.gif *.mp4 *.mov);;"
            "PDF Files (*.pdf);;"
            "Images (*.png *.jpg *.jpeg *.gif);;"
            "Videos (*.mp4 *.mov);;"
            "All Files (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select Media File",
            "",
            filters,
        )
        if not file_path:
            return None
        return Path(file_path)

    def pick_icon_file(self, parent: Optional[QWidget] = None) -> Optional[Path]:
        filters = "Icon Files (*.png *.jpg *.jpeg *.gif);;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select Icon Image",
            "",
            filters,
        )
        if not file_path:
            return None
        return Path(file_path)
