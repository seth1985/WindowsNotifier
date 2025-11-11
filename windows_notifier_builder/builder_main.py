"""
Entry point for the windows_notifier_builder application.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from windows_notifier_builder.windows_notifier_builder.builder_app import BuilderApp


def main() -> int:
    """Launch the builder GUI."""
    app = QApplication(sys.argv)
    builder = BuilderApp()
    builder.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
