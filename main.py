"""Iris application entry point.

Responsible only for wiring things together:
    1. Load configuration.
    2. Set up logging.
    3. Construct the (placeholder, no-op) Aura controller.
    4. Launch the Qt application and a minimal window.

No feature logic belongs here — this file should stay small forever.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from aura.controller import AuraController
from aura.renderer.null_renderer import NullAuraRenderer
from config.settings import get_settings
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    setup_logging(settings.logging)

    logger.info("Starting %s v%s", settings.app_name, settings.version)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.version)

    aura = AuraController(renderer=NullAuraRenderer())
    aura.start()

    window = MainWindow(app_name=settings.app_name, app_version=settings.version)
    window.show()

    exit_code = app.exec()

    aura.stop()
    logger.info("%s exited with code %s", settings.app_name, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
