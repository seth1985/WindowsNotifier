"""
Shared representation of a module instance combining manifest data and resolved assets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .manifest_schema import parse_iso8601_utc


def _looks_like_drive_path(value: str) -> bool:
    return len(value) >= 3 and value[1] == ":" and value[2] in {"/", "\\"}


@dataclass(slots=True)
class ModuleDefinition:
    """
    Encapsulates a module folder, its manifest metadata, and derived fields
    for media resolution and expiry handling.
    """

    root: Path
    manifest: Dict[str, Any]
    media_path: Optional[Path] = field(init=False, default=None)
    media_url: Optional[str] = field(init=False, default=None)
    icon_path: Optional[Path] = field(init=False, default=None)
    icon_url: Optional[str] = field(init=False, default=None)
    icon_preset: Optional[str] = field(init=False, default=None)
    sound: Optional[str] = field(init=False, default=None)
    notification_type: str = field(init=False, default="standard")
    condition_script_path: Optional[Path] = field(init=False, default=None)
    condition_interval_minutes: int = field(init=False, default=60)
    module_key: Optional[str] = field(init=False, default=None)
    scheduled_utc: Optional[datetime] = field(init=False, default=None)
    expires_utc: Optional[datetime] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.module_key = self.root.name
        raw_type = self.manifest.get("type") or "standard"
        if isinstance(raw_type, str):
            self.notification_type = raw_type.lower()
        else:
            self.notification_type = "standard"

        media_reference = self.manifest.get("media")
        if isinstance(media_reference, str) and media_reference.strip():
            self._assign_media(media_reference.strip())

        icon_reference = self.manifest.get("icon")
        if isinstance(icon_reference, str) and icon_reference.strip():
            self._assign_icon(icon_reference.strip())

        sound_value = self.manifest.get("sound")
        if isinstance(sound_value, str) and sound_value.strip():
            self.sound = sound_value.strip()
        else:
            self.sound = None

        if self.notification_type == "conditional":
            script_ref = self.manifest.get("condition_script")
            if isinstance(script_ref, str) and script_ref.strip():
                self.condition_script_path = (self.root / script_ref.strip()).resolve()
            interval_value = self.manifest.get("condition_interval_minutes")
            self.condition_interval_minutes = _coerce_interval(interval_value)

        schedule_value = self.manifest.get("schedule")
        if isinstance(schedule_value, str) and schedule_value.strip():
            self.scheduled_utc = parse_iso8601_utc(schedule_value)
        else:
            self.scheduled_utc = None

        expires_value = self.manifest.get("expires")
        if isinstance(expires_value, str) and expires_value.strip():
            self.expires_utc = parse_iso8601_utc(expires_value)

    def _assign_media(self, reference: str) -> None:
        lowered = reference.lower()
        if lowered.startswith(("https://", "http://")):
            self.media_url = reference
            return
        if lowered.startswith("www."):
            self.media_url = "https://" + reference[4:]
            return
        if reference.startswith("\\") or _looks_like_drive_path(reference):
            self.media_path = Path(reference)
            return
        self.media_path = (self.root / reference).resolve()

    def _assign_icon(self, reference: str) -> None:
        lowered = reference.lower()
        if lowered.startswith("preset:"):
            self.icon_preset = lowered.split(":", 1)[1] or None
            return
        if lowered.startswith(("https://", "http://")):
            self.icon_url = reference
            return
        if lowered.startswith("www."):
            self.icon_url = "https://" + reference[4:]
            return
        if reference.startswith("\\") or _looks_like_drive_path(reference):
            self.icon_path = Path(reference)
            return
        self.icon_path = (self.root / reference).resolve()

    @property
    def title(self) -> str:
        return self.manifest.get("title", "")

    @property
    def message(self) -> str:
        return self.manifest.get("message", "")

    @property
    def category(self) -> str:
        return self.manifest.get("category", "")

    @property
    def scheduled_time(self) -> Optional[datetime]:
        return self.scheduled_utc

    @property
    def sound_setting(self) -> Optional[str]:
        return self.sound

    @property
    def is_conditional(self) -> bool:
        return self.notification_type == "conditional"

    def is_expired(self, *, reference: Optional[datetime] = None) -> bool:
        """Return whether the module has expired."""
        if self.expires_utc is None:
            return False

        reference_dt = reference or datetime.utcnow()
        if reference_dt.tzinfo is None:
            return reference_dt >= self.expires_utc.replace(tzinfo=None)

        return reference_dt >= self.expires_utc


def _coerce_interval(value: Any) -> int:
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = 60
    if interval <= 0:
        interval = 60
    return interval
