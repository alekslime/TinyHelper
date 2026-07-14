"""Bridges Milestone 7 (Part B.3) `VisionModel.locate()` results from the
background vision-inference thread to Qt's main/GUI thread. Same pattern
as `app/llm_bridge.py`, `app/transcript_bridge.py`, and
`app/wake_word_bridge.py` — see those files' docstrings for why this
matters.

`locate()` runs on its own worker thread (not the Qt main thread) for the
same reason LLM generation and transcription do — MiniCPM-V inference is
real, CPU-bound time, and the GUI must not block on it.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class LocateResultBridge(QObject):
    """Emits on the main thread once a `locate()` call has resolved,
    regardless of which thread called `report_found` / `report_not_found`.

    `found=False` and a genuine parse failure (`locate()` returning
    `None`) are deliberately collapsed into the single `not_found` signal
    by the caller before reporting — see `docs/DECISIONS.md`: both mean
    "nothing to point at right now," not two different error states.
    """

    # Real screen pixel coordinates (already converted from locate()'s
    # percent-of-screenshot output) + the model's own label for what it found.
    target_found = Signal(int, int, int, int, str)  # x, y, w, h, label
    target_not_found = Signal()

    def report_found(self, x: int, y: int, w: int, h: int, label: str) -> None:
        """Safe to call from any thread."""
        self.target_found.emit(x, y, w, h, label)

    def report_not_found(self) -> None:
        """Safe to call from any thread."""
        self.target_not_found.emit()
