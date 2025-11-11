"""
Windows registry integration placeholder.

Provides an abstraction that the rest of the application can use to
read and write module state without dealing with win32 APIs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ModuleStatus = Literal["Pending", "Completed"]


@dataclass
class RegistryStore:
    """Facade for registry operations."""

    base_key: str = r"HKCU\Software\WindowsNotifier\Modules"

    def get_status(self, module_id: str) -> Optional[ModuleStatus]:
        """
        Retrieve the persisted module status.

        Currently returns None. The concrete implementation will consult
        the Windows registry via pywin32 APIs.
        """
        # TODO: perform registry read.
        return None

    def set_status(self, module_id: str, status: ModuleStatus) -> None:
        """Persist the module status in the registry."""
        # TODO: perform registry write.

    def delete_module(self, module_id: str) -> None:
        """Remove the module key from the registry."""
        # TODO: remove the registry key if necessary.
        return None
