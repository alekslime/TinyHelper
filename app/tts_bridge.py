"""Bridges TTS playback completion from the background speaking thread to
Qt's main/GUI thread. Same pattern as `app/llm_bridge.py`,
`app/transcript_bridge.py`, and `app/wake_word_bridge.py` — see those
files' docstrings for why this matters.

Playback runs on its own worker thread (not the Qt main thread) because
`TTSEngine.speak()` blocks until audio finishes playing, and the GUI must
not block on it.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class TTSBridge(QObject):
    """Emits on the main thread once playback has finished (naturally, or
    via `TTSEngine.stop()`) or failed, regardless of which thread called
    `report_finished` / `report_failure`.
    """

    finished = Signal()  # playback completed (or was stopped) with no error
    failed = Signal(str)  # human-readable error message

    def report_finished(self) -> None:
        """Callback intended to be passed to the TTS playback pipeline.

        Safe to call from any thread.
        """
        self.finished.emit()

    def report_failure(self, message: str) -> None:
        """Safe to call from any thread."""
        self.failed.emit(message)
