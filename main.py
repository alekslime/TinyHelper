"""Iris application entry point.

Responsible only for wiring things together:
    1. Load configuration.
    2. Set up logging.
    3. Construct the (placeholder, no-op) Aura controller.
    4. Construct voice activation (microphone + wake word detection) and
       bridge its detections onto the Qt main thread.
    5. Launch the Qt application and a minimal window.

No feature logic belongs here — this file should stay small forever.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.wake_word_bridge import WakeWordBridge
from aura.controller import AuraController
from aura.renderer.null_renderer import NullAuraRenderer
from aura.states import AuraState
from config.settings import get_settings
from utils.logger import setup_logging

logger = logging.getLogger(__name__)

# `voice.service` depends on the optional "speech" extras (openwakeword,
# sounddevice) — see pyproject.toml and docs/DECISIONS.md. Import it
# defensively so Iris still launches with just the core dependencies
# installed; voice activation is simply unavailable in that case.
try:
    from voice.service import VoiceActivationService

    _VOICE_AVAILABLE = True
except ImportError:
    VoiceActivationService = None  # type: ignore[assignment,misc]
    _VOICE_AVAILABLE = False


def main() -> int:
    settings = get_settings()
    setup_logging(settings.logging)

    logger.info("Starting %s v%s", settings.app_name, settings.version)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.version)

    aura = AuraController(renderer=NullAuraRenderer())
    aura.start()

    # Bridge: audio thread -> Qt main thread. See app/wake_word_bridge.py.
    wake_word_bridge = WakeWordBridge()

    def on_wake_word_detected(model_name: str, score: float) -> None:
        # Runs on the main thread (Qt queues the signal delivery for us).
        logger.info("Wake word '%s' detected (score=%.3f) — Aura -> LISTENING", model_name, score)
        aura.set_state(AuraState.LISTENING)

    wake_word_bridge.detected.connect(on_wake_word_detected)

    voice_service = None
    if _VOICE_AVAILABLE:
        voice_service = VoiceActivationService(
            settings=settings.voice,
            on_wake_word=wake_word_bridge.report_detection,
        )
        if not voice_service.start():
            logger.warning("Continuing without voice activation this session (see error above).")
            aura.set_state(AuraState.ERROR)
    else:
        logger.warning(
            "Voice activation dependencies not installed (pip install -e '.[speech]') — "
            "continuing without wake word detection this session."
        )

    window = MainWindow(app_name=settings.app_name, app_version=settings.version)
    window.show()

    exit_code = app.exec()

    if voice_service is not None:
        voice_service.stop()
    aura.stop()
    logger.info("%s exited with code %s", settings.app_name, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
