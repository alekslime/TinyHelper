"""Bridges `VisionModel.locate()` found-box results from the background
generation thread to Qt's main/GUI thread. Same pattern as
`app/wake_word_bridge.py`, `app/transcript_bridge.py`, and
`app/llm_bridge.py` -- see those files' docstrings for why this matters.

`locate()` runs on the same worker thread as LLM generation (see
`main.py:_build_prompt_with_screen_context`), not the Qt main thread.
`AuraController.show_target_box()` ultimately touches real Qt widgets
(`GlowAuraRenderer` / `_TargetBoxWidget`), so the actual call has to
happen on the main thread -- this bridge is what gets it there.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class VisionLocateBridge(QObject):
    """Emits `box_found` on the main thread whenever `locate()` finds
    something to point at, regardless of which thread called
    `report_found`.

    There's no `report_not_found` here on purpose -- the not-found /
    parse-failure path doesn't touch Aura's target box at all, it goes
    straight through `LLMResponseBridge.report_failure()` with a retry
    message instead (see `main.py`). This bridge only exists to carry
    real screen-pixel coordinates across the thread boundary for the
    found case.
    """

    box_found = Signal(int, int, int, int)  # (x, y, w, h) in real screen pixels

    def report_found(self, x: int, y: int, w: int, h: int) -> None:
        """Callback intended to be called from the generation worker
        thread once `VisionModel.locate()` returns `found=True` and the
        percent coordinates have been converted to screen pixels.

        Safe to call from any thread.
        """
        self.box_found.emit(x, y, w, h)
