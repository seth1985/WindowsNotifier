"""
Utilities for computing deterministic module identifiers.

The final implementation will hash manifest contents and media bytes to
generate a stable SHA-256 identifier per specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModuleIdentity:
    """Represents the computed identity for a module."""

    module_id: str
    manifest_path: Path
    media_path: Path


def compute_module_id(manifest_path: Path, media_path: Path) -> ModuleIdentity:
    """
    Placeholder for hashing logic.

    Returns a predictable dummy ID to ease early testing. The actual
    implementation will use hashlib.sha256 over manifest content and the
    byte content of the media file.
    """
    dummy_id = f"MODULE-{manifest_path.stem}"
    return ModuleIdentity(module_id=dummy_id, manifest_path=manifest_path, media_path=media_path)
