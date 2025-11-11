"""
Application coordinator orchestrating notification presentation.
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Deque, Optional

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QStyle

from core.idle_monitor import IdleMonitor
from core.module_loader import DEFAULT_SCAN_INTERVAL_SECONDS, LoadResult, scan_modules
from core.notification_popup import NotificationPopup
from core.registry_store import RegistryStore
from core.settings import CoreSettings, CoreSettingsManager
from shared.module_definition import ModuleDefinition
from windows_notifier_core.windows_notifier_core import logger as app_logger

APP_NAME = "Windows Notifier Core"
APP_VERSION = "1.0.0"
APP_PURPOSE = "Displays notifications delivered by your organization."
SCAN_INTERVAL_SECONDS = DEFAULT_SCAN_INTERVAL_SECONDS
SETTINGS_REFRESH_INTERVAL_MS = 15000
DEFAULT_MODULES_DIR = Path(
    os.environ.get(
        "WINDOWS_NOTIFIER_MODULES",
        str(Path.home() / "AppData" / "Local" / "Windows Notifier" / "Modules"),
    )
)

try:
    import winsound
except ModuleNotFoundError:  # pragma: no cover - non-Windows environments
    winsound = None


@dataclass
class AppCoordinator(QObject):
    modules_dir: Path = field(default_factory=lambda: DEFAULT_MODULES_DIR)
    registry: RegistryStore = field(default_factory=RegistryStore)
    settings_manager: CoreSettingsManager = field(default_factory=CoreSettingsManager)

    def __post_init__(self) -> None:
        super().__init__()
        self._logger = app_logger.get_logger()
        self.modules_dir = Path(self.modules_dir)
        self.modules_dir.mkdir(parents=True, exist_ok=True)

        self._modules: Deque[ModuleDefinition] = deque()
        self._current_module: Optional[ModuleDefinition] = None
        self._current_registry_key: Optional[str] = None
        self._manual_shutdown_requested = False

        self._popup = NotificationPopup()
        self._idle_monitor = IdleMonitor()

        self._popup.clicked.connect(self._on_popup_clicked)
        self._popup.closed.connect(self._on_popup_closed)
        self._popup.showMeHow.connect(self._on_show_me_how)
        self._popup.understood.connect(self._on_understood)
        self._popup.remindLater.connect(self._on_remind_later)

        self._idle_monitor.idleReached.connect(self._on_idle_reached)

        self._tray = QSystemTrayIcon(self)
        tray_icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
        self._tray.setIcon(tray_icon)
        self._tray.setToolTip(f"{APP_NAME} v{APP_VERSION}")

        menu = QMenu()
        refresh_action = QAction("Refresh Now", menu)
        exit_action = QAction("Exit", menu)
        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        self._tray.setContextMenu(menu)

        refresh_action.triggered.connect(self._manual_refresh)
        exit_action.triggered.connect(self.shutdown)

        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(SCAN_INTERVAL_SECONDS * 1000)
        self._scan_timer.timeout.connect(self._on_scan_timer)

        self._settings: CoreSettings = CoreSettings()
        self._initial_settings = self.settings_manager.read_settings()
        self._core_active = False
        self._settings_timer = QTimer(self)
        self._settings_timer.setInterval(SETTINGS_REFRESH_INTERVAL_MS)
        self._settings_timer.timeout.connect(self._reload_settings)

    def start(self) -> None:
        self._logger.info("Starting application coordinator. Monitoring %s", self.modules_dir)
        initial_settings = getattr(self, "_initial_settings", CoreSettings())
        self._apply_settings(initial_settings, initial=True)
        self._settings_timer.start()

    def shutdown(self) -> None:
        self._logger.info("Shutting down application on user request.")
        self._manual_shutdown_requested = True
        self._scan_timer.stop()
        self._idle_monitor.stop()
        self._popup.hide()
        self._tray.hide()
        QApplication.instance().quit()

    @property
    def manual_shutdown_requested(self) -> bool:
        return self._manual_shutdown_requested

    def _manual_refresh(self) -> None:
        if not self._settings.enabled:
            self._logger.debug("Manual refresh ignored because core is disabled.")
            return
        self._logger.info("Manual refresh triggered from tray menu.")
        self._refresh_modules()

    def _reload_settings(self) -> None:
        new_settings = self.settings_manager.read_settings()
        if new_settings != self._settings:
            self._logger.info("Detected registry settings change. Applying updates.")
            self._apply_settings(new_settings)

    def _apply_settings(self, settings: CoreSettings, *, initial: bool = False) -> None:
        previous = self._settings
        self._settings = settings

        if not settings.enabled:
            if self._core_active or initial:
                self._logger.info("Core disabled via registry; pausing background work.")
            self._core_active = False
            self._scan_timer.stop()
            self._idle_monitor.stop()
            self._popup.hide()
            if self._tray.isVisible():
                self._tray.hide()
            return

        if settings.show_tray_icon:
            if not self._tray.isVisible():
                self._tray.show()
        else:
            if self._tray.isVisible():
                self._tray.hide()

        interval_ms = max(1, settings.scan_interval_seconds) * 1000
        if self._scan_timer.interval() != interval_ms:
            self._scan_timer.setInterval(interval_ms)

        if not self._core_active:
            self._core_active = True
            self._scan_timer.start()
            self._refresh_modules()
        else:
            if previous.scan_interval_seconds != settings.scan_interval_seconds:
                self._logger.info(
                    "Polling interval updated to %s seconds.",
                    settings.scan_interval_seconds,
                )

    def _refresh_modules(self) -> None:
        if not self._settings.enabled:
            self._logger.debug("Skipping module refresh; core disabled by policy.")
            return
        result = scan_modules(
            self.modules_dir,
            registry=self.registry,
            scan_interval_seconds=self._settings.scan_interval_seconds,
        )
        self._handle_load_result(result)
        if self._current_module is None:
            self._process_next_module()

    def _on_scan_timer(self) -> None:
        self._refresh_modules()

    def _handle_load_result(self, result: LoadResult) -> None:
        for path, error in result.errors:
            self._logger.error("Failed to load module at %s: %s", path, error)

        now = datetime.now(timezone.utc)
        due_list: list[ModuleDefinition] = []
        future_count = 0
        seen_keys: set[str] = set()

        for module in result.modules:
            key = module.module_key or module.root.name
            if key in seen_keys:
                continue
            seen_keys.add(key)

            if key == self._current_registry_key:
                continue

            scheduled = module.scheduled_utc
            if scheduled and scheduled > now:
                future_count += 1
                continue

            due_list.append(module)

        sorted_due = sorted(
            due_list,
            key=lambda m: ((m.scheduled_utc or now), m.title),
        )
        self._modules = deque(sorted_due)
        self._logger.info(
            "Modules ready: %d, waiting for schedule: %d",
            len(self._modules),
            future_count,
        )

    def _process_next_module(self) -> None:
        if self._current_module is not None:
            return

        if not self._modules:
            self._logger.debug("No due modules to display.")
            self._popup.hide()
            return

        while self._modules:
            module = self._modules.popleft()
            key = module.module_key or module.root.name
            self._current_module = module
            self._current_registry_key = key

            hash_fragment = (self.registry.get_module_hash(key) or "unknown")[:8]
            scheduled_info = (
                module.scheduled_utc.isoformat().replace("+00:00", "Z")
                if module.scheduled_utc
                else "immediate"
            )
            self._logger.info(
                "Presenting module %s (key=%s, hash=%s, scheduled=%s)",
                module.title,
                key,
                hash_fragment,
                scheduled_info,
            )
            self._play_sound(module)
            self._popup.show_for(module)
            return

        self._popup.hide()

    def _on_popup_clicked(self) -> None:
        if not self._current_module:
            return
        self._logger.info("Popup clicked for module key=%s", self._current_registry_key)
        self._on_show_me_how()

    def _on_popup_closed(self) -> None:
        self._logger.debug("Popup closed by user or programmatically.")

    def _on_show_me_how(self) -> None:
        if not self._current_module:
            return
        self._logger.info(
            "User requested 'Show me how' for module key=%s",
            self._current_registry_key,
        )
        self._open_module_media(self._current_module)

    def _on_understood(self) -> None:
        if not self._current_module or not self._current_registry_key:
            return
        self._logger.info("User acknowledged module key=%s", self._current_registry_key)
        self.registry.mark_completed(self._current_registry_key)
        self._popup.hide()
        if self._settings.auto_delete_modules:
            self._delete_module_folder(self._current_module.root)
        else:
            self._logger.debug("Auto-delete disabled; leaving module folder in place.")
        self._current_module = None
        self._current_registry_key = None
        self._refresh_modules()

    def _on_remind_later(self) -> None:
        if not self._current_module or not self._current_registry_key:
            return
        new_time = datetime.now(timezone.utc) + timedelta(hours=1)
        iso_value = new_time.isoformat().replace("+00:00", "Z")
        self._logger.info(
            "User selected 'Remind me later' for module key=%s; rescheduled to %s",
            self._current_registry_key,
            iso_value,
        )
        self.registry.set_schedule(self._current_registry_key, new_time)
        self._popup.hide()
        self._idle_monitor.stop()
        self._current_module = None
        self._current_registry_key = None
        self._refresh_modules()

    def _on_idle_reached(self) -> None:
        if not self._current_module:
            return
        self._logger.info(
            "Idle threshold reached. Re-displaying module key=%s",
            self._current_registry_key,
        )
        self._play_sound(self._current_module)
        self._popup.show_for(self._current_module)

    def _play_sound(self, module: ModuleDefinition) -> None:
        if not self._settings.sound_enabled:
            self._logger.debug("Sound playback suppressed by registry setting.")
            return
        if not module or not module.sound_setting:
            return
        if module.sound_setting != "windows_default":
            self._logger.warning("Unsupported sound setting '%s'", module.sound_setting)
            return
        if winsound is None:
            self._logger.warning("winsound module not available; cannot play sound.")
            return

        sound_path = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Media" / "Windows Notify System Generic.wav"
        if not sound_path.exists():
            self._logger.warning("Default notification sound not found at %s", sound_path)
            return

        try:
            winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except RuntimeError as exc:  # pragma: no cover - difficult to simulate
            self._logger.error("Failed to play notification sound: %s", exc)

    def _open_module_media(self, module: ModuleDefinition) -> None:
        if module.media_path and module.media_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(module.media_path)))
            return
        if module.media_url:
            url = module.media_url
            if url.startswith("www."):
                url = "https://" + url[4:]
            QDesktopServices.openUrl(QUrl(url))

    def _delete_module_folder(self, path: Path) -> None:
        self._logger.debug("Deleting module folder %s", path)
        try:
            self._safe_delete_folder(path)
        except OSError as exc:
            self._logger.error("Failed to delete module folder %s: %s", path, exc)

    def _safe_delete_folder(self, path: Path) -> None:
        if not path.exists():
            return

        for child in path.iterdir():
            if child.is_dir():
                self._safe_delete_folder(child)
            else:
                child.unlink(missing_ok=True)
        path.rmdir()


