"""
Persistence layer for module state using the Windows registry.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterator, Optional

import winreg


class ModuleStatus(Enum):
    PENDING = "Pending"
    COMPLETED = "Completed"
    EXPIRED = "Expired"


class ConditionState(Enum):
    WAITING = "Waiting"
    TRIGGERED = "Triggered"
    ERROR = "Error"


@dataclass
class RegistryStore:
    """Thin wrapper over winreg enabling consistent storage of module state."""

    base_subkey: str = r"Software\WindowsNotifier\Modules"
    hive: int = winreg.HKEY_CURRENT_USER
    _winreg = winreg

    def __init__(self, *, hive: Optional[int] = None, winreg_module=winreg) -> None:
        if hive is not None:
            self.hive = hive
        self._winreg = winreg_module

    def get_status(self, key_name: str) -> Optional[ModuleStatus]:
        try:
            with self._open_key(key_name, writable=False) as key:
                value, _ = self._winreg.QueryValueEx(key, "Status")
        except (FileNotFoundError, OSError):
            return None

        try:
            return ModuleStatus(value)
        except ValueError:
            return None

    def get_module_hash(self, key_name: str) -> Optional[str]:
        try:
            with self._open_key(key_name, writable=False) as key:
                value, _ = self._winreg.QueryValueEx(key, "ModuleHash")
                return value
        except (FileNotFoundError, OSError):
            return None

    def set_module_hash(self, key_name: str, module_hash: str) -> None:
        with self._open_key(key_name, writable=True) as key:
            self._winreg.SetValueEx(key, "ModuleHash", 0, self._winreg.REG_SZ, module_hash)

    def get_schedule(self, key_name: str) -> Optional[str]:
        try:
            with self._open_key(key_name, writable=False) as key:
                value, _ = self._winreg.QueryValueEx(key, "ScheduledAt")
                return value
        except (FileNotFoundError, OSError):
            return None

    def set_schedule(self, key_name: str, schedule: Optional[datetime]) -> None:
        with self._open_key(key_name, writable=True) as key:
            if schedule is None:
                try:
                    self._winreg.DeleteValue(key, "ScheduledAt")
                except OSError:
                    pass
            else:
                iso_value = schedule.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                self._winreg.SetValueEx(key, "ScheduledAt", 0, self._winreg.REG_SZ, iso_value)

    def mark_first_seen(self, key_name: str, *, title: Optional[str], category: Optional[str]) -> None:
        with self._open_key(key_name, writable=True) as key:
            now_iso = _utcnow_iso()
            if not self._query_optional(key, "FirstSeen"):
                self._winreg.SetValueEx(key, "FirstSeen", 0, self._winreg.REG_SZ, now_iso)

            self._winreg.SetValueEx(key, "Status", 0, self._winreg.REG_SZ, ModuleStatus.PENDING.value)

            if title:
                self._winreg.SetValueEx(key, "Title", 0, self._winreg.REG_SZ, title)
            if category:
                self._winreg.SetValueEx(key, "Category", 0, self._winreg.REG_SZ, category)

            try:
                self._winreg.DeleteValue(key, "CompletedOn")
            except OSError:
                pass

    def mark_completed(self, key_name: str) -> None:
        with self._open_key(key_name, writable=True) as key:
            self._winreg.SetValueEx(key, "Status", 0, self._winreg.REG_SZ, ModuleStatus.COMPLETED.value)
            self._winreg.SetValueEx(key, "CompletedOn", 0, self._winreg.REG_SZ, _utcnow_iso())

    def mark_expired(self, key_name: str) -> None:
        with self._open_key(key_name, writable=True) as key:
            self._winreg.SetValueEx(key, "Status", 0, self._winreg.REG_SZ, ModuleStatus.EXPIRED.value)

    def get_condition_state(self, key_name: str) -> Optional[ConditionState]:
        try:
            with self._open_key(key_name, writable=False) as key:
                value, _ = self._winreg.QueryValueEx(key, "ConditionState")
        except (FileNotFoundError, OSError):
            return None
        try:
            return ConditionState(value)
        except ValueError:
            return None

    def set_condition_state(self, key_name: str, state: ConditionState) -> None:
        with self._open_key(key_name, writable=True) as key:
            self._winreg.SetValueEx(key, "ConditionState", 0, self._winreg.REG_SZ, state.value)

    def clear_condition_tracking(self, key_name: str) -> None:
        with self._open_key(key_name, writable=True) as key:
            for name in ("ConditionState", "ConditionNextRun", "ConditionError"):
                try:
                    self._winreg.DeleteValue(key, name)
                except OSError:
                    pass

    def get_condition_next_run(self, key_name: str) -> Optional[datetime]:
        try:
            with self._open_key(key_name, writable=False) as key:
                value, _ = self._winreg.QueryValueEx(key, "ConditionNextRun")
        except (FileNotFoundError, OSError):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def set_condition_next_run(self, key_name: str, when: datetime) -> None:
        with self._open_key(key_name, writable=True) as key:
            iso_value = when.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            self._winreg.SetValueEx(key, "ConditionNextRun", 0, self._winreg.REG_SZ, iso_value)

    def set_condition_error(self, key_name: str, message: str) -> None:
        with self._open_key(key_name, writable=True) as key:
            self._winreg.SetValueEx(key, "ConditionError", 0, self._winreg.REG_SZ, message[:1024])
            self._winreg.SetValueEx(key, "ConditionState", 0, self._winreg.REG_SZ, ConditionState.ERROR.value)

    @contextmanager
    def _open_key(self, key_name: str, *, writable: bool) -> Iterator:
        subkey = f"{self.base_subkey}\\{key_name}"
        access = self._winreg.KEY_READ
        if writable:
            access |= self._winreg.KEY_WRITE

        try:
            key = self._winreg.OpenKey(self.hive, subkey, 0, access)
        except FileNotFoundError:
            if not writable:
                raise
            key = self._winreg.CreateKey(self.hive, subkey)
        try:
            yield key
        finally:
            self._winreg.CloseKey(key)

    def _query_optional(self, key, value_name: str) -> Optional[str]:
        try:
            value, _ = self._winreg.QueryValueEx(key, value_name)
            return value
        except OSError:
            return None


def _utcnow_iso() -> str:
    """Return a UTC ISO-8601 timestamp without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
