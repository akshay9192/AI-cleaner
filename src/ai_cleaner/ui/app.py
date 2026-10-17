"""Desktop entry point; the complete workflow is added in milestone M9."""

from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    application = QApplication.instance() or QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("AI-cleaner")
    window.setCentralWidget(QLabel("Choose a project folder to begin."))
    window.resize(760, 480)
    window.show()
    return application.exec()
