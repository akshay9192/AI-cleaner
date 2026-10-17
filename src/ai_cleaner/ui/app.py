"""Desktop entry point; the complete workflow is added in milestone M9."""

from __future__ import annotations

import sys
from pathlib import Path


def main(*, root: Path | None = None, state_override: Path | None = None) -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    application = QApplication.instance() or QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("AI-cleaner")
    del state_override
    message = f"Selected project: {root}" if root else "Choose a project folder to begin."
    window.setCentralWidget(QLabel(message))
    window.resize(760, 480)
    window.show()
    return application.exec()
