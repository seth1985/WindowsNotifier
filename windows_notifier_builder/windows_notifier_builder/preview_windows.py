"""
Preview helpers leveraging the core UI components.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QWidget

from core.notification_popup import NotificationPopup
from shared.module_definition import ModuleDefinition

try:
    import winsound
except ModuleNotFoundError:  # pragma: no cover
    winsound = None


class PreviewPanel(QWidget):
    """Simple button panel exposing preview actions."""

    previewPopup = Signal()
    previewContent = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        popup_btn = QPushButton("Preview Popup")
        content_btn = QPushButton("Open Media")

        layout.addWidget(popup_btn)
        layout.addWidget(content_btn)

        popup_btn.clicked.connect(self.previewPopup)  # type: ignore[arg-type]
        content_btn.clicked.connect(self.previewContent)  # type: ignore[arg-type]


class PreviewCoordinator(QObject):
    """Utility that shows preview actions using production widgets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup = NotificationPopup()
        self._parent_widget = parent

    def preview_popup(self, module: ModuleDefinition) -> None:
        self._play_sound(module)
        self._popup.show_for(module)

    def preview_content(self, module: ModuleDefinition) -> None:
        if module.media_path and module.media_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(module.media_path)))
            return
        if module.media_url:
            url = module.media_url
            if url.startswith("www."):
                url = "https://" + url[4:]
            QDesktopServices.openUrl(QUrl(url))
            return
        QMessageBox.information(self._parent_widget, "Preview", "No media associated with this module.")

    def _play_sound(self, module: ModuleDefinition) -> None:
        if winsound is None:
            return
        if not module.sound_setting or module.sound_setting != "windows_default":
            return
        sound_path = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Media" / "Windows Notify System Generic.wav"
        if not sound_path.exists():
            return
        try:
            winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except RuntimeError:
            pass
