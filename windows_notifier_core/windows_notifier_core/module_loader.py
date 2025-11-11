"""
Module scanning and lifecycle placeholder.

Responsible for discovering module folders, parsing manifests, and
coordinating registry and expiry logic. Implementation will be filled
in later; for now we define structural contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from shared.module_definition import ModuleDefinition


@dataclass
class ModuleLoader:
    """Skeleton loader that describes the API expected by CoreApp."""

    modules_dir: Path = Path("./Modules")

    def scan_modules(self) -> List[ModuleDefinition]:
        """
        Discover module folders within the modules directory.

        Returns an empty list for now; final implementation will parse
        manifests, compute IDs, and filter according to registry state.
        """
        # TODO: perform file-system scanning and manifest parsing.
        return []

    def watch_for_changes(self) -> None:
        """
        Hook for future file-system monitoring (e.g., watchdog integration).
        """
        # TODO: add watchdog observer integration.
        return None

    def _load_manifest(self, module_path: Path) -> ModuleDefinition | None:
        """Placeholder for manifest parsing logic."""
        # TODO: parse manifest.json and validate against schema.
        return None

    def available_media(self, module: ModuleDefinition) -> Iterable[Path]:
        """Placeholder describing how media files will be enumerated."""
        # TODO: return the media file path(s) for the module.
        return []
