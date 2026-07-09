"""Bridges wake word detections from the audio callback thread to Qt's
main/GUI thread.

`sounddevice`'s audio callback runs on its own background thread, not Qt's
main thread. Qt objects (and, later, GPU-rendered Aura) must only be
touched from the main thread. Rather than calling Aura/UI code directly
from the audio thread, we emit a Qt signal — Qt automatically marshals
signal emissions across threads to the receiving object's thread via its
event loop, as long as the connection uses `QueuedConnection` (the default
when emitter and receiver live on different threads).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class WakeWordBridge(QObject):
    """Emits `detected` on the main thread whenever a wake word fires,
    regardless of which thread called `report_detection`.
    """

    detected = Signal(str, float)  # (model_name, confidence_score)

    def report_detection(self, model_name: str, score: float) -> None:
        """Callback intended to be passed to `VoiceActivationService`.

        Safe to call from any thread — emitting `detected` here queues the
        signal for delivery on this `WakeWordBridge` instance's thread
        (the main thread, since it's constructed there).
        """
        self.detected.emit(model_name, score)
