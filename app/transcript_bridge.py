"""Bridges transcription results from the background transcription thread
to Qt's main/GUI thread. Same pattern as `app/wake_word_bridge.py` — see
that file's docstring for why this matters.

Transcription runs on its own worker thread (not the audio thread, not the
main thread — see `voice/service.py`) because it can take a noticeable
moment, and neither the audio callback nor the GUI should block on it.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class TranscriptBridge(QObject):
    """Emits on the main thread once an utterance has been transcribed
    (or determined to contain no speech), regardless of which thread
    called `report_transcript`.
    """

    transcribed = Signal(str)  # non-empty recognized text
    no_speech_detected = Signal()  # utterance captured but nothing recognized

    def report_transcript(self, text: str) -> None:
        """Callback intended to be passed to the transcription pipeline.

        Safe to call from any thread.
        """
        if text:
            self.transcribed.emit(text)
        else:
            self.no_speech_detected.emit()
