"""
Utility for packaging modules into Intune .intunewin archives.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from . import logger


class IntunePackager:
    """Runs the Microsoft IntuneWinAppUtil to wrap module folders."""

    def __init__(
        self,
        *,
        modules_dir: Path,
        tool_path: Path | None = None,
        install_script: Path | None = None,
    ) -> None:
        self.modules_dir = modules_dir.resolve()
        self.tool_path = (tool_path or (self.modules_dir / "IntuneWinAppUtil.exe")).resolve()
        self.install_script = (install_script or (self.modules_dir / "install_module_intune.ps1")).resolve()
        self.output_dir = (self.modules_dir / "IntunePackages").resolve()
        self._logger = logger.get_logger()

    def package(self, module_paths: Iterable[Path]) -> Path:
        modules = [path.resolve() for path in module_paths]
        if not modules:
            raise ValueError("Select at least one module to package.")

        for module in modules:
            if not module.exists():
                raise FileNotFoundError(f"Module folder '{module}' not found.")
            if self.modules_dir not in module.parents and module != self.modules_dir:
                raise ValueError(f"Module '{module}' must live under {self.modules_dir}.")

        if not self.tool_path.exists():
            raise FileNotFoundError(
                f"IntuneWinAppUtil.exe not found at {self.tool_path}. Place the tool next to your Modules folder."
            )
        if not self.install_script.exists():
            raise FileNotFoundError(
                f"install_module_intune.ps1 not found at {self.install_script}. Copy it into the Modules directory."
            )

        staging_dir = Path(tempfile.mkdtemp(prefix="intune_pkg_"))
        self._logger.info("Creating Intune package staging folder at %s", staging_dir)
        try:
            for module in modules:
                destination = staging_dir / module.name
                self._logger.info("Copying module %s to staging area", module)
                shutil.copytree(module, destination)

            shutil.copy2(self.install_script, staging_dir / self.install_script.name)

            self.output_dir.mkdir(parents=True, exist_ok=True)
            default_package = self.output_dir / f"{self.install_script.stem}.intunewin"
            if default_package.exists():
                default_package.unlink()

            cmd = [
                str(self.tool_path),
                "-c",
                str(staging_dir),
                "-s",
                self.install_script.name,
                "-o",
                str(self.output_dir),
                "-q",
            ]
            self._logger.info("Running IntuneWinAppUtil: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(
                    "IntuneWinAppUtil failed with exit code %s:\n%s\n%s"
                    % (result.returncode, result.stdout, result.stderr)
                )

            if not default_package.exists():
                raise FileNotFoundError(
                    f"Expected output '{default_package.name}' not found in {self.output_dir}."
                )

            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            if len(modules) == 1:
                base = modules[0].name
            else:
                base = f"modules_{len(modules)}"
            final_name = f"{base}_{timestamp}.intunewin"
            final_path = self.output_dir / final_name
            if final_path.exists():
                final_path.unlink()
            default_package.rename(final_path)
            self._logger.info("Created Intune package %s", final_path)
            return final_path
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)
