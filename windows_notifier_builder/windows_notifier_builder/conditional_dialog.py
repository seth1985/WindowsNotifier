"""
Dialog for configuring conditional notification scripts.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QDateTimeEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ConditionalDialog(QDialog):
    """Collects condition script settings for a notification."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conditional Notification")
        self.setModal(True)
        self._script_path: Optional[Path] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        script_row = QHBoxLayout()
        self._script_label = QLabel("No script selected")
        self._script_label.setObjectName("ScriptPathLabel")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse_script)
        script_row.addWidget(self._script_label, 1)
        script_row.addWidget(browse_button)
        layout.addLayout(script_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Recheck interval (minutes):"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 4 * 24 * 60)
        self._interval_spin.setValue(60)
        interval_row.addWidget(self._interval_spin)
        layout.addLayout(interval_row)

        expiry_row = QHBoxLayout()
        expiry_row.addWidget(QLabel("Expiration (UTC):"))
        self._expires_edit = QDateTimeEdit(QDateTime.currentDateTimeUtc().addSecs(3600))
        self._expires_edit.setCalendarPopup(True)
        self._expires_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        expiry_row.addWidget(self._expires_edit)
        layout.addLayout(expiry_row)

        test_button = QPushButton("Test Script")
        test_button.clicked.connect(self._test_script)
        layout.addWidget(test_button, alignment=Qt.AlignmentFlag.AlignLeft)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Use Script")
        save_button.clicked.connect(self._handle_accept)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def _browse_script(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PowerShell Script",
            "",
            "PowerShell Scripts (*.ps1);;All Files (*.*)",
        )
        if not file_path:
            return
        self._script_path = Path(file_path)
        self._script_label.setText(str(self._script_path))

    def _test_script(self) -> None:
        if not self._script_path:
            QMessageBox.warning(self, "Select Script", "Choose a PowerShell script before testing.")
            return
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(self._script_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            QMessageBox.critical(self, "Script Error", f"Failed to execute script:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Script Result",
            (
                f"Exit code: {result.returncode}\n\n"
                f"Standard Output:\n{result.stdout or '(none)'}\n\n"
                f"Standard Error:\n{result.stderr or '(none)'}"
            ),
        )

    def _handle_accept(self) -> None:
        if not self._script_path:
            QMessageBox.warning(self, "Select Script", "Choose a PowerShell script before saving.")
            return
        if not self._validate_expiration():
            return
        self.accept()

    @property
    def script_path(self) -> Optional[Path]:
        return self._script_path

    @property
    def interval_minutes(self) -> int:
        return self._interval_spin.value()

    @property
    def expires_iso(self) -> str:
        qdt = self._expires_edit.dateTime().toUTC()
        dt = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")

    def _validate_expiration(self) -> bool:
        expires_dt = datetime.fromtimestamp(self._expires_edit.dateTime().toUTC().toSecsSinceEpoch(), tz=timezone.utc)
        if expires_dt <= datetime.now(timezone.utc):
            QMessageBox.warning(self, "Invalid Expiration", "Choose an expiration time in the future.")
            return False
        return True
