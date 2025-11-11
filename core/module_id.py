"""
Module identifier utilities.

Derives a stable SHA-256 digest from manifest data and referenced media.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from shared.module_definition import ModuleDefinition


def compute_module_id(module: ModuleDefinition) -> str:
    """
    Compute a deterministic SHA-256 hash for the provided module.

    The manifest dict is canonicalised to JSON with sorted keys and
    compact separators. Media content (either file bytes or URL string)
    is folded into the same digest to ensure updates are reflected.
    """
    digest = hashlib.sha256()

    manifest_json = json.dumps(module.manifest, sort_keys=True, separators=(",", ":"))
    digest.update(manifest_json.encode("utf-8"))

    if module.media_path is not None:
        digest.update(_read_file_bytes(module.media_path))
    elif module.media_url is not None:
        digest.update(module.media_url.encode("utf-8"))

    if module.icon_path is not None:
        digest.update(_read_file_bytes(module.icon_path))
    elif module.icon_url is not None:
        digest.update(module.icon_url.encode("utf-8"))

    return digest.hexdigest()


def _read_file_bytes(path: Path) -> bytes:
    """Read file bytes, raising a descriptive error if unavailable."""
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"File not found for module ID computation: {path}") from exc
