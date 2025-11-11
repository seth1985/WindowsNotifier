"""
Media viewer factory bridging ModuleDefinition assets to Qt widgets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QMovie, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - optional dependency
    QWebEngineView = None  # type: ignore

try:
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
except ImportError:  # pragma: no cover - optional dependency
    QMediaPlayer = None  # type: ignore
    QVideoWidget = None  # type: ignore

from shared.module_definition import ModuleDefinition


def choose_viewer(module: ModuleDefinition) -> QWidget:
    """
    Return an appropriate widget for presenting the module's media asset.
    """
    if module.media_url:
        QDesktopServices.openUrl(QUrl(module.media_url))
        return _build_message_widget("Opened external content in default browser.")

    if module.media_path:
        suffix = module.media_path.suffix.lower()
        if suffix == ".pdf" and QWebEngineView is not None:
            return _build_pdf_viewer(module.media_path)
        if suffix in {".mp4", ".mov"} and QMediaPlayer is not None and QVideoWidget is not None:
            return _build_video_player(module.media_path)
        if suffix in {".png", ".jpg", ".jpeg"}:
            return _build_image_viewer(module.media_path)
        if suffix == ".gif":
            return _build_gif_viewer(module.media_path)

    return _build_message_widget("No preview available for this media.")


def _build_message_widget(message: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel(message)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    return widget


def _build_pdf_viewer(path: Path) -> QWidget:
    view = QWebEngineView()
    view.setUrl(QUrl.fromLocalFile(str(path)))
    return view


def _build_video_player(path: Path) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    video_widget = QVideoWidget(container)
    layout.addWidget(video_widget)
    player = QMediaPlayer(container)
    player.setVideoOutput(video_widget)
    player.setSource(QUrl.fromLocalFile(str(path)))
    container._media_player = player  # type: ignore[attr-defined]
    return container


def _build_image_viewer(path: Path) -> QWidget:
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        label.setText("Image unavailable.")
    else:
        label.setPixmap(pixmap)
    return label


def _build_gif_viewer(path: Path) -> QWidget:
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    movie = QMovie(str(path))
    if movie.isValid():
        label.setMovie(movie)
        movie.start()
    else:
        label.setText("Animation unavailable.")
    return label
