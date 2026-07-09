"""Ties microphone capture and wake word detection together into one
runnable service.

This is the piece `main.py` starts and stops. It owns the lifecycle of the
mic stream and the detector, and reports wake word detections upward via a
callback — it does not know or care what happens after a detection (that's
main.py's job, e.g. transitioning Aura to LISTENING).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from config.schema import VoiceSettings
from voice.audio_stream import MicrophoneStream
from voice.wake_word import WakeWordDetector

logger = logging.getLogger(__name__)

WakeWordDetectedCallback = Callable[[str, float], None]


class VoiceActivationService:
    """Owns the mic stream + wake word detector lifecycle."""

    def __init__(self, settings: VoiceSettings, on_wake_word: WakeWordDetectedCallback) -> None:
        self._settings = settings
        self._on_wake_word = on_wake_word

        self._detector = WakeWordDetector(
            model_name_or_path=settings.wake_word_model,
            on_detected=self._handle_detection,
            threshold=settings.detection_threshold,
            consecutive_frames_required=settings.consecutive_frames_required,
        )
        self._mic = MicrophoneStream(
            on_frame=self._detector.process_frame,
            device=settings.input_device,
        )

    def _handle_detection(self, model_name: str, score: float) -> None:
        self._on_wake_word(model_name, score)

    def start(self) -> bool:
        """Begin listening for the wake word. Call once during app startup.

        Returns True if voice activation started successfully, False if it
        could not (e.g. no microphone present, permission denied). Iris
        should continue running without voice activation in that case
        rather than crashing — the rest of the app doesn't depend on it.
        """
        logger.info("Voice activation starting (wake word model: %s)", self._settings.wake_word_model)
        try:
            self._mic.start()
        except Exception:
            logger.exception(
                "Failed to start microphone stream — voice activation will be unavailable "
                "this session. Check that a microphone is connected and accessible."
            )
            return False
        return True

    def stop(self) -> None:
        """Stop listening. Call once during app shutdown."""
        self._mic.stop()
        logger.info("Voice activation stopped.")
