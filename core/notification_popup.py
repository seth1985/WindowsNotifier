"""
Notification popup window presented in the bottom-right corner with action icons.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from shared.module_definition import ModuleDefinition

ASSETS_DIR = Path(__file__).resolve().parent / "Assets"
IDEA_ICON_PATH = ASSETS_DIR / "idea.png"
BUILDER_IDEA_ICON_PATH = (
    Path(__file__).resolve().parents[2] / "windows_notifier_builder" / "windows_notifier_builder" / "Assets" / "idea.png"
)


class NotificationPopup(QWidget):
    clicked = Signal()
    closed = Signal()
    showMeHow = Signal()
    understood = Signal()
    remindLater = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent)
        self.setWindowFlags(flags)
        self.setWindowFlag(Qt.WindowType.ToolTip, False)
        self.setObjectName("NotificationPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.90)

        self._container = QWidget(self)
        self._container.setObjectName("PopupCard")
        shadow = QGraphicsDropShadowEffect(self._container)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 140))
        shadow.setOffset(0, 10)
        self._container.setGraphicsEffect(shadow)

        self._module: ModuleDefinition | None = None

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(48, 48)
        self._icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self._default_pixmap = icon.pixmap(48, 48)
        self._icon_label.setPixmap(self._default_pixmap)

        self._title_label = QLabel()
        self._title_label.setObjectName("NotificationTitle")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self._message_label = QLabel()
        self._message_label.setWordWrap(True)
        self._message_label.setObjectName("NotificationMessage")
        self._message_label.setMaximumWidth(360)

        actions_row = QWidget()
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 6, 0, 0)
        actions_layout.setSpacing(10)
        actions_layout.addStretch()
        self._show_button = self._create_action_button(
            QStyle.StandardPixmap.SP_MessageBoxInformation, "Show me more"
        )
        self._understand_button = self._create_action_button(
            QStyle.StandardPixmap.SP_DialogApplyButton, "I understand"
        )
        self._remind_button = self._create_action_button(
            QStyle.StandardPixmap.SP_BrowserReload, "Remind me"
        )
        actions_layout.addWidget(self._show_button)
        actions_layout.addWidget(self._understand_button)
        actions_layout.addWidget(self._remind_button)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.addWidget(self._title_label)
        text_layout.addWidget(self._message_label)
        text_layout.addWidget(actions_row)

        base_layout = QHBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.addWidget(self._container)

        layout = QHBoxLayout(self._container)
        layout.addWidget(self._icon_label)
        layout.addLayout(text_layout)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)
        self.setMinimumWidth(340)
        self.setMaximumWidth(460)

        self.setStyleSheet(
            """
            QWidget#PopupCard {
                background-color: rgba(24, 24, 28, 0.78);
                color: white;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.10);
            }
            QWidget#PopupCard QLabel#NotificationTitle {
                color: white;
            }
            QWidget#PopupCard QLabel#NotificationMessage {
                color: rgba(255, 255, 255, 0.85);
                margin-top: 2px;
            }
            """
        )

        self._show_button.clicked.connect(self.showMeHow)  # type: ignore[arg-type]
        self._understand_button.clicked.connect(self.understood)  # type: ignore[arg-type]
        self._remind_button.clicked.connect(self.remindLater)  # type: ignore[arg-type]

    def _create_action_button(self, standard_icon: QStyle.StandardPixmap, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setAutoRaise(False)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setIconSize(QSize(26, 26))
        button.setFixedSize(44, 44)
        button.setIcon(self.style().standardIcon(standard_icon))
        button.setStyleSheet(
            """
            QToolButton {
                background-color: rgba(255, 255, 255, 0.12);
                border-radius: 21px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.22);
            }
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 0.30);
            }
            """
        )
        return button

    def show_for(self, module: ModuleDefinition) -> None:
        """Populate the popup with module data and display it."""
        self._module = module
        self._title_label.setText(module.title)
        self._message_label.setText(module.message)
        self._apply_icon(module)
        self.adjustSize()
        self._position_bottom_right()
        self.show()

    def _apply_icon(self, module: ModuleDefinition) -> None:
        pixmap: QPixmap | None = None
        if module.icon_preset:
            if module.icon_preset == "idea":
                idea_source = IDEA_ICON_PATH if IDEA_ICON_PATH.exists() else BUILDER_IDEA_ICON_PATH
                idea_pixmap = QPixmap(str(idea_source)) if idea_source.exists() else QPixmap()
                if not idea_pixmap.isNull():
                    self._icon_label.setPixmap(
                        idea_pixmap.scaled(
                            48,
                            48,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    return
            preset_map = {
                "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
                "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
                "reminder": QStyle.StandardPixmap.SP_BrowserReload,
                "idea": QStyle.StandardPixmap.SP_FileDialogDetailedView,
            }
            standard_icon = preset_map.get(module.icon_preset, QStyle.StandardPixmap.SP_MessageBoxInformation)
            icon_pixmap = self.style().standardIcon(standard_icon).pixmap(48, 48)
            self._icon_label.setPixmap(icon_pixmap)
            return
        if module.icon_path and module.icon_path.exists():
            pixmap = QPixmap(str(module.icon_path))
        elif module.icon_url:
            temp_pix = QPixmap()
            if temp_pix.load(module.icon_url):
                pixmap = temp_pix
        if pixmap and not pixmap.isNull():
            self._icon_label.setPixmap(
                pixmap.scaled(
                    48,
                    48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._icon_label.setPixmap(self._default_pixmap)

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.right() - self.width() - 20
        y = geometry.bottom() - self.height() - 20
        self.move(QPoint(x, y))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)

