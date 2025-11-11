"""
Manifest schema validation utilities shared by the core runtime and builder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class ManifestValidationError(ValueError):
    """Raised when a manifest file is missing required data or is malformed."""


@dataclass(frozen=True)
class ManifestConstraints:
    """Schema constraints as simple dataclass constants."""

    max_title_length: int = 120
    max_message_length: int = 240
    default_category: str = "General"


def load_and_validate_manifest(path: Path) -> Dict[str, Any]:
    """
    Load a manifest JSON file and validate it against the expected schema.

    Returns a normalized manifest dictionary with defaults applied and the
    expires field expressed as an ISO-8601 string in UTC (if provided).
    """
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManifestValidationError(f"Manifest file not found: {path}") from exc
    except OSError as exc:
        raise ManifestValidationError(f"Unable to read manifest: {path}") from exc

    try:
        raw_manifest = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"Manifest is not valid JSON: {exc}") from exc

    if not isinstance(raw_manifest, dict):
        raise ManifestValidationError("Manifest root must be a JSON object.")

    constraints = ManifestConstraints()

    title = _require_string(
        raw_manifest.get("title"),
        field="title",
        max_length=constraints.max_title_length,
        required=True,
    )

    message = _require_string(
        raw_manifest.get("message"),
        field="message",
        max_length=240,
        required=True,
    )

    category = raw_manifest.get("category")
    if category is None or (isinstance(category, str) and category.strip() == ""):
        category = constraints.default_category
    else:
        category = _require_string(category, field="category", required=False)

    media = raw_manifest.get("media")
    media_value = _validate_optional_asset(raw_manifest.get("media"), field="media")

    expires_raw = raw_manifest.get("expires")
    expires_iso: Optional[str] = None
    if expires_raw is not None:
        expires_value = _require_string(expires_raw, field="expires", required=False)
        if not expires_value:
            expires_iso = None
        else:
            expires_dt = parse_iso8601_utc(expires_value)
            expires_iso = _format_utc_iso(expires_dt)

    schedule_raw = raw_manifest.get("schedule")
    schedule_iso: Optional[str] = None
    if schedule_raw is not None:
        schedule_value = _require_string(schedule_raw, field="schedule", required=False)
        if schedule_value:
            schedule_dt = parse_iso8601_utc(schedule_value)
            schedule_iso = _format_utc_iso(schedule_dt)

    icon_value = _validate_optional_asset(raw_manifest.get("icon"), field="icon")
    sound_value = _validate_optional_sound(raw_manifest.get("sound"))

    notification_type = raw_manifest.get("type", "standard")
    notification_type = _require_string(notification_type, field="type", required=False) or "standard"
    notification_type = notification_type.lower()
    if notification_type not in {"standard", "conditional"}:
        raise ManifestValidationError("type must be either 'standard' or 'conditional'.")

    condition_script = None
    condition_interval = None
    if notification_type == "conditional":
        condition_script = _validate_condition_script(raw_manifest.get("condition_script"))
        condition_interval = _validate_condition_interval(raw_manifest.get("condition_interval_minutes"))

    normalized = {
        "title": title,
        "message": message,
        "category": category,
        "media": media_value,
        "icon": icon_value,
        "sound": sound_value,
        "schedule": schedule_iso,
        "expires": expires_iso,
        "type": notification_type,
        "condition_script": condition_script,
        "condition_interval_minutes": condition_interval,
    }

    return normalized


def parse_iso8601_utc(value: str) -> datetime:
    """
    Parse a subset of ISO-8601 formatted timestamps that must be UTC.

    Accepts values ending with 'Z' or explicit '+00:00' offsets. Raises
    ManifestValidationError when parsing fails or when timezone is not UTC.
    """
    if not isinstance(value, str):
        raise ManifestValidationError("expires must be a string.")

    cleaned = value.strip()
    try:
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ManifestValidationError(
            "expires must be in ISO-8601 format (e.g. 2026-01-01T00:00:00Z)."
        ) from exc

    if dt.tzinfo is None:
        raise ManifestValidationError("expires must include a timezone in UTC.")

    offset = dt.utcoffset()
    if offset != timezone.utc.utcoffset(None):
        raise ManifestValidationError("expires must be specified in UTC.")

    dt_utc = dt.astimezone(timezone.utc)

    return dt_utc


def _format_utc_iso(dt: datetime) -> str:
    """Return a canonical UTC ISO-8601 string with trailing 'Z'."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_string(
    value: Any,
    *,
    field: str,
    max_length: Optional[int] = None,
    required: bool,
) -> str:
    """Validate that a value is a string in accordance with constraints."""
    if value is None:
        if required:
            raise ManifestValidationError(f"{field} is required.")
        return ""

    if not isinstance(value, str):
        raise ManifestValidationError(f"{field} must be a string.")

    stripped = value.strip()
    if required and stripped == "":
        raise ManifestValidationError(f"{field} must be a non-empty string.")

    if max_length is not None and len(stripped) > max_length:
        raise ManifestValidationError(
            f"{field} must be at most {max_length} characters."
        )

    return stripped


def _validate_optional_asset(value: Any, *, field: str) -> Optional[str]:
    if value is None:
        return None
    asset = _require_string(value, field=field, required=False)
    if not asset:
        return None

    if asset.startswith("preset:"):
        return asset

    lowered = asset.lower()
    if lowered.startswith(("https://", "http://")):
        return asset
    if lowered.startswith("www."):
        return "https://" + asset

    if asset.startswith("\\\\"):
        cleaned = asset.replace("/", "\\")
        cleaned = cleaned.lstrip("\\")
        return "\\\\" + cleaned

    if asset.startswith("/"):
        raise ManifestValidationError(_build_asset_error(field))

    if _looks_like_drive_path(asset):
        return asset

    if "://" in asset:
        raise ManifestValidationError(_build_asset_error(field))

    path = Path(asset)
    if path.is_absolute() or ".." in path.parts:
        raise ManifestValidationError(_build_asset_error(field))

    return asset


def _validate_optional_sound(value: Any) -> Optional[str]:
    if value is None:
        return None
    sound = _require_string(value, field="sound", required=False)
    if not sound:
        return None
    allowed = {"windows_default"}
    if sound not in allowed:
        raise ManifestValidationError(
            "sound must be one of: windows_default."
        )
    return sound


def _looks_like_drive_path(value: str) -> bool:
    return len(value) >= 3 and value[1] == ":" and value[2] in {"/", "\\"}


def _build_asset_error(field: str) -> str:
    supported = (
        "relative file path",
        "preset:<name>",
        "http:// or https:// URL",
        "www. URL",
        "UNC/share path (e.g. \\\\server\\share)",
        "drive path (e.g. C:\\folder\\file)",
    )
    return (
        f"{field} must be one of the supported types: "
        + ", ".join(supported)
        + "."
    )


def _validate_condition_script(value: Any) -> str:
    script = _require_string(value, field="condition_script", required=True)
    if not script.endswith(".ps1"):
        raise ManifestValidationError("condition_script must reference a PowerShell (.ps1) file.")

    path = Path(script)
    if path.is_absolute() or ".." in path.parts:
        raise ManifestValidationError("condition_script must be a relative path without traversal.")

    return script


def _validate_condition_interval(value: Any) -> int:
    if value is None:
        return 60
    if isinstance(value, bool):
        raise ManifestValidationError("condition_interval_minutes must be a positive integer.")
    try:
        interval = int(value)
    except (TypeError, ValueError) as exc:
        raise ManifestValidationError("condition_interval_minutes must be a positive integer.") from exc
    if interval <= 0:
        raise ManifestValidationError("condition_interval_minutes must be greater than zero.")
    return interval





