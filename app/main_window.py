"""Minimal placeholder application window.

Per the project's UX philosophy, Iris should ultimately feel like part of
the OS rather than a traditional app window — this window exists only to
prove the application launches for Milestone 1. It is expected to be
replaced or hidden by default once the Aura overlay and tray-based
interaction model are built.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Placeholder window shown during early development milestones."""

    def __init__(self, app_name: str, app_version: str) -> None:
        super().__init__()
        self.setWindowTitle(f"{app_name} v{app_version}")
        self.resize(480, 240)

        central = QWidget(self)
        layout = QVBoxLayout(central)

        status_label = QLabel(
            f"{app_name} v{app_version} is running.\n\n"
            "This placeholder window will be replaced by the Aura overlay\n"
            "and tray-based interaction model in a later milestone.",
            self,
        )
        layout.addWidget(status_label)

        self.setCentralWidget(central)
        logger.debug("MainWindow constructed.")
