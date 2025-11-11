"""
Form window for authoring module manifests.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDateTime, QSize, Qt, QSignalBlocker, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from shared.manifest_schema import ManifestValidationError, load_and_validate_manifest

from .conditional_dialog import ConditionalDialog
from .media_picker import MediaPicker


ASSETS_DIR = Path(__file__).resolve().parent / "Assets"
IDEA_ICON_PATH = ASSETS_DIR / "idea.png"


# ---------------------------------------------------------------------------#
# Data model
# ---------------------------------------------------------------------------#


@dataclass
class FormData:
    """Represents the validated data collected from the form."""

    manifest: dict
    media_file_path: Optional[Path]
    media_url: Optional[str]
    icon_file_path: Optional[Path]
    icon_url: Optional[str]
    icon_preset: Optional[str]
    sound: Optional[str]
    schedule: Optional[str]
    condition_script_path: Optional[Path] = None
    condition_interval_minutes: Optional[int] = None


# ---------------------------------------------------------------------------#
# Main form
# ---------------------------------------------------------------------------#


class ManifestForm(QWidget):
    """
    Collects manifest fields, handles validation, and exposes signals for
    saving and previewing modules.
    """

    saveRequested = Signal(object)
    previewPopupRequested = Signal(object)
    previewContentRequested = Signal(object)
    intunePackageRequested = Signal(list)

    def __init__(
        self,
        *,
        media_picker: Optional[MediaPicker] = None,
        modules_dir: Path | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ManifestForm")
        self.setWindowTitle("Windows Notifier Module Builder")
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.setMinimumWidth(540)

        self.media_picker = media_picker or MediaPicker()
        self._selected_media_path: Optional[Path] = None
        self._selected_icon_path: Optional[Path] = None
        self._modules_dir = Path(modules_dir or "./Modules").resolve()

        self._build_ui()
        self._connect_dynamic_signals()

        # Initialise dependent UI state.
        self.media_type_changed()
        self.icon_type_changed()
        self.schedule_toggle()
        self.update_char_counter()
        self._refresh_preview()

    # ------------------------------------------------------------------#
    # UI construction helpers
    # ------------------------------------------------------------------#

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 16)
        main_layout.setSpacing(10)

        header_row = QHBoxLayout()

        self._intune_button = QPushButton("Create Intune Package")
        self._intune_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._intune_button.setObjectName("IntuneButton")
        self._intune_button.clicked.connect(self._open_intune_dialog)
        header_row.addWidget(self._intune_button)

        header_row.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        info_menu = QMenu("Info", self)
        info_menu.addAction("About", self._show_about_dialog)
        info_menu.addAction("Readme", self._open_readme)

        self._info_button = QToolButton()
        self._info_button.setText("Info")
        self._info_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._info_button.setMenu(info_menu)
        self._info_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._info_button.setObjectName("InfoButton")
        header_row.addWidget(self._info_button)

        main_layout.addLayout(header_row)

        # Title / message / category
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(12)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Enter a concise title")
        self._title_input.setMaxLength(36)
        form_layout.addRow("Title*", self._title_input)

        self._message_input = QTextEdit()
        self._message_input.setPlaceholderText("Maximum 240 characters")
        self._message_input.setFixedHeight(140)
        form_layout.addRow("Message*", self._message_input)

        self._message_counter = QLabel("0 / 240")
        self._message_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.addRow("", self._message_counter)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(self._create_divider())

        # Schedule + expiration section
        schedule_container = QVBoxLayout()
        schedule_container.setSpacing(8)

        schedule_row = QHBoxLayout()
        schedule_row.setSpacing(8)
        self._schedule_checkbox = QCheckBox("Schedule first display")
        self._schedule_edit = QDateTimeEdit(QDateTime.currentDateTimeUtc())
        self._schedule_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._schedule_edit.setCalendarPopup(True)
        schedule_row.addWidget(self._schedule_checkbox)
        schedule_row.addWidget(self._schedule_edit)
        schedule_container.addLayout(schedule_row)

        expires_row = QHBoxLayout()
        expires_row.setSpacing(8)
        self._expires_checkbox = QCheckBox("Set expiration")
        self._expires_edit = QDateTimeEdit(QDateTime.currentDateTimeUtc())
        self._expires_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._expires_edit.setCalendarPopup(True)
        self._expires_edit.setEnabled(False)
        self._expires_checkbox.toggled.connect(self._expires_edit.setEnabled)  # type: ignore[arg-type]
        expires_row.addWidget(self._expires_checkbox)
        expires_row.addWidget(self._expires_edit)
        schedule_container.addLayout(expires_row)

        main_layout.addLayout(schedule_container)
        main_layout.addWidget(self._create_divider())

        # Media + icon section
        media_icon_row = QHBoxLayout()
        media_icon_row.setSpacing(24)

        media_column = QVBoxLayout()
        media_column.setSpacing(6)
        media_label = QLabel("Media")
        media_label.setProperty("sectionTitle", "true")
        media_column.addWidget(media_label)

        media_buttons_row = QHBoxLayout()
        media_buttons_row.setSpacing(10)
        self._media_group = QButtonGroup(self)
        self._media_none = QRadioButton("None")
        self._media_file = QRadioButton("File")
        self._media_link = QRadioButton("Link")
        self._media_none.setChecked(True)

        for button in (self._media_none, self._media_file, self._media_link):
            self._media_group.addButton(button)
            media_buttons_row.addWidget(button)

        media_buttons_row.addStretch()
        media_column.addLayout(media_buttons_row)

        self._sound_checkbox = QCheckBox("Play Windows notification sound")
        media_column.addWidget(self._sound_checkbox)
        media_icon_row.addLayout(media_column, 2)

        icon_column = QVBoxLayout()
        icon_column.setSpacing(6)
        icon_label = QLabel("Notification icon")
        icon_label.setProperty("sectionTitle", "true")
        icon_column.addWidget(icon_label)

        icon_row = QHBoxLayout()
        icon_row.setSpacing(8)
        self._icon_combo = QComboBox()
        self._icon_combo.addItem("Default (Info)", "preset:info")
        self._icon_combo.addItem("Warning", "preset:warning")
        self._icon_combo.addItem("Reminder", "preset:reminder")
        self._icon_combo.addItem("Idea", "preset:idea")
        self._icon_combo.insertSeparator(self._icon_combo.count())
        self._icon_combo.addItem("Upload Icon File", "file")
        self._icon_combo.addItem("Icon from URL", "url")

        icon_row.addWidget(self._icon_combo, 1)

        self._icon_preview = QLabel()
        self._icon_preview.setFixedSize(54, 54)
        self._icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_preview.setObjectName("IconPreview")
        icon_row.addWidget(self._icon_preview)

        icon_column.addLayout(icon_row)
        media_icon_row.addLayout(icon_column, 1)
        main_layout.addLayout(media_icon_row)
        main_layout.addWidget(self._create_divider())

        self._media_file_controls = QWidget()
        file_controls_layout = QHBoxLayout(self._media_file_controls)
        file_controls_layout.setContentsMargins(0, 0, 0, 0)
        file_controls_layout.setSpacing(6)
        self._media_path_label = QLabel("No file selected")
        self._media_path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        media_browse_button = QPushButton("Browse…")
        media_browse_button.clicked.connect(self._browse_media_file)
        file_controls_layout.addWidget(self._media_path_label)
        file_controls_layout.addWidget(media_browse_button)
        main_layout.addWidget(self._media_file_controls)

        self._media_link_controls = QWidget()
        link_controls_layout = QHBoxLayout(self._media_link_controls)
        link_controls_layout.setContentsMargins(0, 0, 0, 0)
        link_controls_layout.setSpacing(6)
        self._media_url_input = QLineEdit()
        self._media_url_input.setPlaceholderText("https://…")
        link_controls_layout.addWidget(self._media_url_input)
        main_layout.addWidget(self._media_link_controls)

        self._icon_file_controls = QWidget()
        icon_file_layout = QHBoxLayout(self._icon_file_controls)
        icon_file_layout.setContentsMargins(0, 0, 0, 0)
        icon_file_layout.setSpacing(6)
        self._icon_path_label = QLabel("No icon selected")
        self._icon_path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        icon_browse_button = QPushButton("Browse…")
        icon_browse_button.clicked.connect(self._browse_icon_file)
        icon_file_layout.addWidget(self._icon_path_label)
        icon_file_layout.addWidget(icon_browse_button)
        main_layout.addWidget(self._icon_file_controls)

        self._icon_url_controls = QWidget()
        icon_url_layout = QHBoxLayout(self._icon_url_controls)
        icon_url_layout.setContentsMargins(0, 0, 0, 0)
        icon_url_layout.setSpacing(6)
        self._icon_url_input = QLineEdit()
        self._icon_url_input.setPlaceholderText("https://…")
        icon_url_layout.addWidget(self._icon_url_input)
        main_layout.addWidget(self._icon_url_controls)

        main_layout.addWidget(self._create_divider())

        # Footer buttons
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self._conditional_button = QPushButton("Save Conditional…")
        footer.addWidget(self._conditional_button)
        footer.addStretch()
        self._save_button = QPushButton("Save Module")
        footer.addWidget(self._save_button)

        main_layout.addLayout(footer)

        # Status message
        self._status_label = QLabel("")
        self._status_label.setObjectName("StatusLabel")
        main_layout.addWidget(self._status_label)

        # Live preview section
        preview_caption = QLabel("Live preview")
        preview_caption.setProperty("sectionTitle", "true")
        main_layout.addWidget(preview_caption)

        self._preview_container = QFrame()
        self._preview_container.setObjectName("PreviewContainer")
        preview_layout = QVBoxLayout(self._preview_container)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)

        preview_header = QHBoxLayout()
        preview_header.setSpacing(12)
        self._preview_icon = QLabel()
        self._preview_icon.setFixedSize(48, 48)
        self._preview_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_icon.setObjectName("PreviewIcon")

        text_column = QVBoxLayout()
        text_column.setSpacing(4)
        self._preview_title = QLabel("Notification Title")
        self._preview_title.setObjectName("PreviewTitle")
        self._preview_message = QLabel("Notification message will appear here.")
        self._preview_message.setWordWrap(True)
        self._preview_message.setObjectName("PreviewMessage")
        text_column.addWidget(self._preview_title)
        text_column.addWidget(self._preview_message)

        preview_header.addWidget(self._preview_icon)
        preview_header.addLayout(text_column)

        preview_layout.addLayout(preview_header)

        preview_actions = QHBoxLayout()
        preview_actions.setSpacing(10)
        preview_actions.addStretch()
        self._preview_show = self._create_preview_action_button(
            QStyle.StandardPixmap.SP_MessageBoxInformation, "Show me more"
        )
        self._preview_understand = self._create_preview_action_button(
            QStyle.StandardPixmap.SP_DialogApplyButton, "I understand"
        )
        self._preview_remind = self._create_preview_action_button(
            QStyle.StandardPixmap.SP_BrowserReload, "Remind me"
        )
        preview_actions.addWidget(self._preview_show)
        preview_actions.addWidget(self._preview_understand)
        preview_actions.addWidget(self._preview_remind)
        preview_layout.addLayout(preview_actions)

        main_layout.addWidget(self._preview_container)

        self._apply_styles()

        # Wire footer buttons to public stubs.
        self._save_button.clicked.connect(self.save)
        self._conditional_button.clicked.connect(self._handle_conditional_request)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#ManifestForm {
                background-color: #1d1d23;
                color: #f2f2f5;
            }
            QLabel[sectionTitle="true"] {
                font-weight: 600;
                margin-top: 6px;
            }
            QLineEdit, QTextEdit, QDateTimeEdit, QComboBox {
                background-color: #2b2b33;
                border: 1px solid #3f3f50;
                border-radius: 6px;
                padding: 4px;
                color: #f2f2f5;
            }
            QTextEdit {
                padding: 6px;
            }
            QCheckBox, QRadioButton {
                padding: 2px;
            }
            QPushButton {
                background-color: #3c3c4a;
                color: #f2f2f5;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4b4b5d;
            }
            QPushButton:pressed {
                background-color: #32323f;
            }
            QLabel#StatusLabel {
                color: #a8a8b5;
                min-height: 18px;
            }
            QFrame#PreviewContainer {
                background-color: #24242c;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.10);
            }
            QLabel#PreviewTitle {
                font-weight: 600;
                font-size: 14px;
            }
            QLabel#PreviewMessage {
                color: rgba(240, 240, 245, 0.85);
            }
            QLabel#PreviewIcon {
                background-color: rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
            QToolButton#InfoButton {
                background: none;
                border: none;
                color: #f2f2f5;
                padding: 4px 8px;
            }
            QToolButton#InfoButton::menu-indicator {
                image: none;
            }
            QLabel#IconPreview {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
            }
            """
        )

    def _create_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedHeight(2)
        line.setStyleSheet("background-color: #9c5cff; border: none; margin: 6px 0;")
        return line

    def _create_preview_action_button(self, icon_name: QStyle.StandardPixmap, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setIcon(self.style().standardIcon(icon_name))
        button.setIconSize(QSize(26, 26))
        button.setToolTip(tooltip)
        button.setFixedSize(44, 44)
        button.setStyleSheet(
            """
            QToolButton {
                background-color: rgba(255, 255, 255, 0.12);
                border-radius: 22px;
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

    def _connect_dynamic_signals(self) -> None:
        self._message_input.textChanged.connect(self.update_char_counter)
        self._message_input.textChanged.connect(self._refresh_preview)
        self._title_input.textChanged.connect(self._refresh_preview)
        self._icon_combo.currentIndexChanged.connect(self.icon_type_changed)
        self._icon_url_input.textChanged.connect(self._refresh_preview)
        self._schedule_checkbox.toggled.connect(self.schedule_toggle)
        for button in (self._media_none, self._media_file, self._media_link):
            button.toggled.connect(self.media_type_changed)

    # ------------------------------------------------------------------#
    # Dynamic behaviour stubs
    # ------------------------------------------------------------------#

    def media_type_changed(self) -> None:
        """Update media controls when the user chooses None/File/Link."""
        if self._media_none.isChecked():
            choice = "none"
        elif self._media_file.isChecked():
            choice = "file"
        else:
            choice = "link"

        self._media_file_controls.setVisible(choice == "file")
        self._media_link_controls.setVisible(choice == "link")

        if choice != "file":
            self._selected_media_path = None
            self._media_path_label.setText("No file selected")
        if choice != "link":
            self._media_url_input.clear()

    def icon_type_changed(self) -> None:
        """Update icon controls and preview when the selection changes."""
        mode = self._icon_combo.currentData()
        self._icon_file_controls.setVisible(mode == "file")
        self._icon_url_controls.setVisible(mode == "url")

        if mode != "file":
            self._selected_icon_path = None
            self._icon_path_label.setText("No icon selected")
        if mode != "url":
            self._icon_url_input.clear()

        self._update_icon_preview()
        self._refresh_preview()

    def schedule_toggle(self) -> None:
        """Enable/disable schedule picker."""
        checked = self._schedule_checkbox.isChecked()
        self._schedule_edit.setEnabled(checked)

    def update_char_counter(self) -> None:
        """Keep the message text within 240 characters and refresh counter."""
        text = self._message_input.toPlainText()
        if len(text) > 240:
            blocker = QSignalBlocker(self._message_input)
            try:
                trimmed = text[:240]
                self._message_input.setPlainText(trimmed)
                cursor = self._message_input.textCursor()
                cursor.setPosition(len(trimmed))
                self._message_input.setTextCursor(cursor)
                text = trimmed
            finally:
                del blocker
        self._message_counter.setText(f"{len(text)} / 240")

    def preview_notification(self) -> None:
        """Emit previewPopupRequested with current form data."""
        try:
            data = self._collect_form_data()
        except (ValueError, ManifestValidationError) as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return
        self.previewPopupRequested.emit(data)

    def save(self) -> None:
        """Emit saveRequested with current form data."""
        try:
            data = self._collect_form_data()
        except (ValueError, ManifestValidationError) as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return
        self.saveRequested.emit(data)

    # ------------------------------------------------------------------#
    # UI helpers
    # ------------------------------------------------------------------#

    def _preview_media_content(self) -> None:
        """Emit previewContentRequested with current form data."""
        try:
            data = self._collect_form_data()
        except (ValueError, ManifestValidationError) as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return
        self.previewContentRequested.emit(data)

    def _browse_media_file(self) -> None:
        path = self.media_picker.pick_media_file(parent=self)
        if path:
            self._selected_media_path = path
            self._media_path_label.setText(str(path))
        else:
            self._media_path_label.setText("No file selected")

    def _browse_icon_file(self) -> None:
        path = self.media_picker.pick_icon_file(parent=self)
        if path:
            self._selected_icon_path = path
            self._icon_path_label.setText(str(path))
        else:
            self._selected_icon_path = None
            self._icon_path_label.setText("No icon selected")
        self._update_icon_preview()
        self._refresh_preview()

    def _handle_conditional_request(self) -> None:
        try:
            base_data = self._collect_form_data()
        except (ValueError, ManifestValidationError) as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return

        dialog = ConditionalDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        script_path = dialog.script_path
        if script_path is None:
            return

        interval = dialog.interval_minutes

        manifest = dict(base_data.manifest)
        manifest["type"] = "conditional"
        manifest["condition_script"] = script_path.name
        manifest["condition_interval_minutes"] = interval
        manifest["expires"] = dialog.expires_iso

        normalized = self._validate_manifest(manifest)
        normalized["condition_script"] = script_path.name
        normalized["condition_interval_minutes"] = interval
        normalized["expires"] = dialog.expires_iso

        conditional_data = FormData(
            manifest=normalized,
            media_file_path=base_data.media_file_path,
            media_url=base_data.media_url,
            icon_file_path=base_data.icon_file_path,
            icon_url=base_data.icon_url,
            icon_preset=base_data.icon_preset,
            sound=base_data.sound,
            schedule=normalized.get("schedule"),
            condition_script_path=script_path,
            condition_interval_minutes=interval,
        )

        self.saveRequested.emit(conditional_data)

    def _update_icon_preview(self) -> None:
        icon = self._resolve_icon_for_preview(self._icon_combo.currentData())
        if icon:
            self._icon_preview.setPixmap(icon.pixmap(48, 48))
        else:
            self._icon_preview.clear()

    def _resolve_icon_for_preview(self, mode: str | None) -> Optional[QIcon]:
        if isinstance(mode, str) and mode.startswith("preset:"):
            preset_name = mode.split(":", 1)[1]
            mapping = {
                "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
                "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
                "reminder": QStyle.StandardPixmap.SP_BrowserReload,
            }
            if preset_name == "idea" and IDEA_ICON_PATH.exists():
                return QIcon(str(IDEA_ICON_PATH))
            standard = mapping.get(preset_name, QStyle.StandardPixmap.SP_MessageBoxInformation)
            return self.style().standardIcon(standard)
        if mode == "file" and self._selected_icon_path:
            return QIcon(str(self._selected_icon_path))
        if mode == "url":
            return self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        return self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)

    def _refresh_preview(self) -> None:
        """Update the live preview card."""
        title = self._title_input.text().strip() or "Notification Title"
        message = self._message_input.toPlainText().strip() or "Notification message will appear here."

        self._preview_title.setText(title)
        self._preview_message.setText(message)

        icon = self._resolve_icon_for_preview(self._icon_combo.currentData())
        if icon:
            self._preview_icon.setPixmap(icon.pixmap(48, 48))
        else:
            self._preview_icon.clear()

    def set_status_message(self, message: str) -> None:
        self._status_label.setText(message)

    # ------------------------------------------------------------------#
    # Data handling
    # ------------------------------------------------------------------#

    def _collect_form_data(self) -> FormData:
        manifest = {
            "title": self._title_input.text().strip(),
            "message": self._message_input.toPlainText().strip(),
            "category": "General",
        }

        if not manifest["title"]:
            raise ValueError("Title is required.")
        if not manifest["message"]:
            raise ValueError("Message is required.")

        if self._expires_checkbox.isChecked():
            manifest["expires"] = self._current_expiry_iso()
        else:
            manifest.pop("expires", None)

        media_file: Optional[Path] = None
        media_url: Optional[str] = None
        if self._media_file.isChecked():
            if not self._selected_media_path:
                raise ValueError("Select a media file or choose a different option.")
            media_file = self._selected_media_path
            manifest["media"] = media_file.name
        elif self._media_link.isChecked():
            media_url = self._media_url_input.text().strip()
            if not media_url:
                raise ValueError("Enter a media link or choose a different option.")
            manifest["media"] = media_url
        else:
            manifest.pop("media", None)

        icon_file: Optional[Path] = None
        icon_url: Optional[str] = None
        icon_preset: Optional[str] = None
        icon_mode = self._icon_combo.currentData()
        if isinstance(icon_mode, str) and icon_mode.startswith("preset:"):
            icon_preset = icon_mode.split(":", 1)[1]
            manifest["icon"] = f"preset:{icon_preset}"
        elif icon_mode == "file":
            if not self._selected_icon_path:
                raise ValueError("Choose an icon file or select another option.")
            icon_file = self._selected_icon_path
            manifest["icon"] = icon_file.name
        elif icon_mode == "url":
            icon_url = self._icon_url_input.text().strip()
            if not icon_url:
                raise ValueError("Enter an icon URL or select another option.")
            manifest["icon"] = icon_url
        else:
            manifest.pop("icon", None)

        schedule_value: Optional[str] = None
        if self._schedule_checkbox.isChecked():
            schedule_value = self._current_schedule_iso()
            manifest["schedule"] = schedule_value
        else:
            manifest.pop("schedule", None)

        sound_value: Optional[str] = None
        if self._sound_checkbox.isChecked():
            sound_value = "windows_default"
            manifest["sound"] = sound_value
        else:
            manifest.pop("sound", None)

        normalized = self._validate_manifest(manifest)

        return FormData(
            manifest=normalized,
            media_file_path=media_file,
            media_url=media_url,
            icon_file_path=icon_file,
            icon_url=icon_url,
            icon_preset=icon_preset,
            sound=sound_value,
            schedule=normalized.get("schedule"),
            condition_script_path=None,
            condition_interval_minutes=None,
        )

    def _validate_manifest(self, manifest: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            return load_and_validate_manifest(manifest_path)

    def _current_expiry_iso(self) -> str:
        qdt = self._expires_edit.dateTime().toUTC()
        dt = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")

    def _current_schedule_iso(self) -> str:
        qdt = self._schedule_edit.dateTime().toUTC()
        dt = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")

    # ------------------------------------------------------------------#
    # Menu actions
    # ------------------------------------------------------------------#

    def _show_about_dialog(self) -> None:
        QMessageBox.information(
            self,
            "About Windows Notifier Builder",
            "Windows Notifier Module Builder\n"
            "Developer: Bojan Crvenkovic\n\n"
            "Use this tool to author notification modules for the Windows Notifier core app.",
        )

    def _open_readme(self) -> None:
        readme_path = Path(__file__).resolve().parents[1] / "README.md"
        if readme_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(readme_path)))
        else:
            QMessageBox.information(self, "Readme Not Found", "README.md could not be located.")

    def _open_intune_dialog(self) -> None:
        dialog = IntunePackageDialog(self._modules_dir, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            modules = dialog.selected_modules()
            if modules:
                self.intunePackageRequested.emit([str(path) for path in modules])


class IntunePackageDialog(QDialog):
    """Dialog presenting available modules for Intune packaging."""

    def __init__(self, modules_dir: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Intune Package")
        self.modules_dir = modules_dir

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        layout = QVBoxLayout(self)
        description = QLabel("Select one or more modules to include in the Intune package:")
        layout.addWidget(description)
        layout.addWidget(self._list)

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

        self._populate_modules()

    def _populate_modules(self) -> None:
        if not self.modules_dir.exists():
            item = QListWidgetItem(f"Modules directory not found: {self.modules_dir}")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
            self._list.setEnabled(False)
            self._button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        module_paths = sorted(
            [path for path in self.modules_dir.iterdir() if path.is_dir() and (path / "manifest.json").exists()],
            key=lambda p: p.name.lower(),
        )

        if not module_paths:
            item = QListWidgetItem("No modules found. Save a module first.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
            self._list.setEnabled(False)
            self._button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        for path in module_paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._list.addItem(item)

    def _on_accept(self) -> None:
        if not self.selected_modules():
            QMessageBox.information(self, "No Modules Selected", "Select at least one module to continue.")
            return
        self.accept()

    def selected_modules(self) -> list[Path]:
        modules: list[Path] = []
        for item in self._list.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, str):
                modules.append(Path(data))
        return modules
