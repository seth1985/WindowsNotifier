"""
Registry-backed configuration for the Windows Notifier Core runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import winreg

from core.module_loader import DEFAULT_SCAN_INTERVAL_SECONDS
from windows_notifier_core.windows_notifier_core import logger as app_logger

_LOGGER = app_logger.get_logger()

_BASE_SUBKEY = r"Software\WindowsNotifier\Core"
_MIN_SCAN_INTERVAL = 60
_MAX_SCAN_INTERVAL = 3600


@dataclass(eq=True)
class CoreSettings:
    enabled: bool = True
    scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL_SECONDS
    show_tray_icon: bool = True
    sound_enabled: bool = True
    auto_delete_modules: bool = True


class CoreSettingsManager:
    """Loads persisted settings from HKCU and clamps invalid data."""

    def __init__(self, *, hive: Optional[int] = None, winreg_module=winreg) -> None:
        self.hive = hive or winreg.HKEY_CURRENT_USER
        self._winreg = winreg_module

    def read_settings(self) -> CoreSettings:
        key = self._open_key()
        if key is None:
            return CoreSettings()

        try:
            return CoreSettings(
                enabled=self._read_bool(key, "IsEnabled", True),
                scan_interval_seconds=self._read_scan_interval(key),
                show_tray_icon=self._read_bool(key, "ShowTrayIcon", True),
                sound_enabled=self._read_bool(key, "SoundEnabled", True),
                auto_delete_modules=self._read_bool(key, "AutoDeleteModules", True),
            )
        finally:
            self._winreg.CloseKey(key)

    def _open_key(self):
        try:
            return self._winreg.OpenKey(self.hive, _BASE_SUBKEY, 0, self._winreg.KEY_READ)
        except FileNotFoundError:
            return None

    def _read_bool(self, key, name: str, default: bool) -> bool:
        raw = self._read_dword(key, name)
        if raw is None:
            return default
        return bool(raw)

    def _read_scan_interval(self, key) -> int:
        raw = self._read_dword(key, "PollingIntervalSeconds")
        if raw is None:
            return DEFAULT_SCAN_INTERVAL_SECONDS
        if raw < _MIN_SCAN_INTERVAL or raw > _MAX_SCAN_INTERVAL:
            _LOGGER.warning(
                "Invalid polling interval %s found in registry. Clamping to safe bounds.",
                raw,
            )
        return max(_MIN_SCAN_INTERVAL, min(_MAX_SCAN_INTERVAL, raw))

    def _read_dword(self, key, name: str) -> Optional[int]:
        try:
            value, value_type = self._winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        if value_type != self._winreg.REG_DWORD:
            _LOGGER.warning("Registry value %s has unexpected type %s.", name, value_type)
            return None
        return int(value)
