"""
Overlay dialog offering next-step actions for a notification.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.module_definition import ModuleDefinition


class ModuleOverlay(QDialog):
    showMeHow = Signal()
    understood = Signal()
    remindLater = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setWindowOpacity(0.95)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 12)
        self.setGraphicsEffect(shadow)

        self._module: ModuleDefinition | None = None

        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self._message_label = QLabel()
        self._message_label.setWordWrap(True)

        self._show_me_how_btn = QPushButton("Show me how")
        self._understood_btn = QPushButton("I understand")
        self._remind_later_btn = QPushButton("Remind me later")

        for btn in (self._show_me_how_btn, self._understood_btn, self._remind_later_btn):
            btn.setMinimumHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                """
                QPushButton {
                    padding: 0 14px;
                    border-radius: 10px;
                    background-color: #2563eb;
                    color: white;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QPushButton:pressed {
                    background-color: #1e40af;
                }
                """
            )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self._title_label)
        layout.addWidget(self._message_label)
        layout.addSpacing(16)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch()
        button_row.addWidget(self._show_me_how_btn)
        button_row.addWidget(self._understood_btn)
        button_row.addWidget(self._remind_later_btn)
        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #111827;
                color: white;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            QLabel {
                color: white;
            }
            """
        )

        self._show_me_how_btn.clicked.connect(self._emit_show_me_how)  # type: ignore[arg-type]
        self._understood_btn.clicked.connect(self._emit_understood)  # type: ignore[arg-type]
        self._remind_later_btn.clicked.connect(self._emit_remind_later)  # type: ignore[arg-type]

    def present(self, module: ModuleDefinition) -> None:
        """Display the overlay for the provided module."""
        self._module = module
        self._title_label.setText(module.title)
        self._message_label.setText(module.message)
        self.adjustSize()
        self._position_bottom_right()
        self.show()

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.right() - self.width() - 30
        y = geometry.bottom() - self.height() - 30
        self.move(QPoint(x, y))

    def _emit_show_me_how(self) -> None:
        self.showMeHow.emit()

    def _emit_understood(self) -> None:
        self.understood.emit()

    def _emit_remind_later(self) -> None:
        self.remindLater.emit()
