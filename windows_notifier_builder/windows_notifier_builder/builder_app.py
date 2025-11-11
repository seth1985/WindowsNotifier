"""
Main application controller for the builder UI.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from shared.module_definition import ModuleDefinition

from . import logger
from .manifest_form import FormData, ManifestForm
from .media_picker import MediaPicker
from .module_writer import ModuleWriter
from .preview_windows import PreviewCoordinator
from .intune_packager import IntunePackager


class BuilderApp(QObject):
    """Coordinates the builder workflow."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._logger = logger.get_logger()
        self._media_picker = MediaPicker()
        self._module_writer = ModuleWriter()
        self._preview = PreviewCoordinator()
        self._packager = IntunePackager(modules_dir=self._module_writer.modules_dir)
        self._form = ManifestForm(media_picker=self._media_picker, modules_dir=self._module_writer.modules_dir)

        self._form.saveRequested.connect(self._handle_save)  # type: ignore[arg-type]
        self._form.previewPopupRequested.connect(self._handle_preview_popup)  # type: ignore[arg-type]
        self._form.previewContentRequested.connect(self._handle_preview_content)  # type: ignore[arg-type]
        self._form.intunePackageRequested.connect(self._handle_intune_package)  # type: ignore[arg-type]

    def start(self) -> None:
        """Display the primary window."""
        self._logger.info("Starting builder application UI.")
        self._form.show()

    def _handle_save(self, data: FormData) -> None:
        try:
            result = self._module_writer.write(data)
        except Exception as exc:  # pragma: no cover - GUI error path
            self._logger.exception("Failed to write module: %s", exc)
            QMessageBox.critical(self._form, "Save Error", str(exc))
            return

        self._logger.info("Module saved to %s (ID: %s)", result.module_path, result.module_id)
        self._form.set_status_message(f"Saved to {result.module_path} (ID: {result.module_id})")
        QMessageBox.information(
            self._form,
            "Module Saved",
            f"Module saved to {result.module_path}\nModule ID: {result.module_id}",
        )

    def _handle_preview_popup(self, data: FormData) -> None:
        module = self._build_preview_module(data)
        self._preview.preview_popup(module)

    def _handle_preview_content(self, data: FormData) -> None:
        module = self._build_preview_module(data)
        self._preview.preview_content(module)

    def _handle_intune_package(self, module_paths: list[str]) -> None:
        if not module_paths:
            return
        try:
            package_path = self._packager.package(Path(path) for path in module_paths)
        except Exception as exc:  # pragma: no cover - GUI error path
            self._logger.exception("Failed to create Intune package: %s", exc)
            QMessageBox.critical(self._form, "Intune Packaging Failed", str(exc))
            return

        self._logger.info("Intune package created at %s", package_path)
        QMessageBox.information(
            self._form,
            "Intune Package Created",
            f"Package created at:\n{package_path}",
        )

    def _build_preview_module(self, data: FormData) -> ModuleDefinition:
        manifest = dict(data.manifest)
        root_candidates = [
            path.parent for path in (data.media_file_path, data.icon_file_path) if path is not None
        ]
        root = root_candidates[0] if root_candidates else Path(".")

        module = ModuleDefinition(root=root, manifest=manifest)
        if data.media_file_path:
            module.media_path = data.media_file_path
        if data.icon_file_path:
            module.icon_path = data.icon_file_path
        if data.icon_preset:
            module.icon_preset = data.icon_preset
        return module
