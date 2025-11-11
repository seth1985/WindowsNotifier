"""
Handles writing manifest and media files to the Modules directory.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.module_id import compute_module_id
from shared.manifest_schema import load_and_validate_manifest
from shared.module_definition import ModuleDefinition

from .manifest_form import FormData

ASSETS_DIR = Path(__file__).resolve().parent / "Assets"
IDEA_ICON = ASSETS_DIR / "idea.png"


@dataclass
class ModuleWriteResult:
    module: ModuleDefinition
    module_id: str
    module_path: Path


@dataclass
class ModuleWriter:
    """Persist manifest and media assets for a module."""

    modules_dir: Path = Path("./Modules")

    def write(self, data: FormData) -> ModuleWriteResult:
        self.modules_dir.mkdir(parents=True, exist_ok=True)

        manifest = dict(data.manifest)
        target_dir = self._create_unique_folder(manifest["title"])

        media_destination = None
        if data.media_file_path:
            media_name = data.media_file_path.name
            media_destination = target_dir / media_name
            shutil.copy2(data.media_file_path, media_destination)
            manifest["media"] = media_name

        if data.icon_preset:
            if data.icon_preset == "idea" and IDEA_ICON.exists():
                icon_name = "icon_idea.png"
                shutil.copy2(IDEA_ICON, target_dir / icon_name)
                manifest["icon"] = icon_name
            else:
                manifest["icon"] = f"preset:{data.icon_preset}"
        elif data.icon_file_path:
            icon_name = data.icon_file_path.name
            shutil.copy2(data.icon_file_path, target_dir / icon_name)
            manifest["icon"] = icon_name

        if data.sound:
            manifest["sound"] = data.sound
        if data.schedule:
            manifest["schedule"] = data.schedule

        if manifest.get("type") == "conditional":
            if not data.condition_script_path:
                raise ValueError("Conditional modules require a PowerShell script.")
            script_name = data.condition_script_path.name
            shutil.copy2(data.condition_script_path, target_dir / script_name)
            manifest["condition_script"] = script_name
            manifest["condition_interval_minutes"] = (
                data.condition_interval_minutes or manifest.get("condition_interval_minutes") or 60
            )
        else:
            manifest.pop("condition_script", None)
            manifest.pop("condition_interval_minutes", None)

        manifest_to_write = {key: value for key, value in manifest.items() if value is not None}

        manifest_path = target_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_to_write, indent=2), encoding="utf-8")

        normalized = load_and_validate_manifest(manifest_path)
        module = ModuleDefinition(root=target_dir, manifest=normalized)
        if media_destination:
            module.media_path = media_destination

        module_id = compute_module_id(module)

        return ModuleWriteResult(module=module, module_id=module_id, module_path=target_dir)

    def _create_unique_folder(self, title: str) -> Path:
        slug_base = self._slugify(title)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        base_name = f"{timestamp}-{slug_base}"

        idx = 0
        while True:
            folder_name = base_name if idx == 0 else f"{base_name}-{idx}"
            target = self.modules_dir / folder_name
            if not target.exists():
                target.mkdir(parents=True)
                return target
            idx += 1

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
        return slug or "module"
