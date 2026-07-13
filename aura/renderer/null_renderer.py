"""A no-op `AuraRenderer` implementation.

Used as the default renderer until the real GPU-rendered ambient glow is
implemented in a later milestone. This lets the rest of the application
(the AuraController, state transitions, etc.) be built and tested now
without any actual rendering existing yet.
"""

from __future__ import annotations

import logging

from aura.renderer.base import AuraRenderer
from aura.states import AuraState

logger = logging.getLogger(__name__)


class NullAuraRenderer(AuraRenderer):
    """Logs what it would do instead of rendering anything."""

    def __init__(self) -> None:
        self._visible: bool = False
        self._state: AuraState = AuraState.IDLE

    def initialize(self) -> None:
        logger.debug("NullAuraRenderer initialized (no visuals — placeholder only).")

    def set_state(self, state: AuraState) -> None:
        logger.debug("Aura state change: %s -> %s", self._state.value, state.value)
        self._state = state

    def show_target_box(self, x: int, y: int, w: int, h: int) -> None:
        logger.debug("NullAuraRenderer.show_target_box(%d, %d, %d, %d) called (no-op).", x, y, w, h)

    def clear_target_box(self) -> None:
        logger.debug("NullAuraRenderer.clear_target_box() called (no-op).")

    def show(self) -> None:
        self._visible = True
        logger.debug("NullAuraRenderer.show() called (no-op).")

    def hide(self) -> None:
        self._visible = False
        logger.debug("NullAuraRenderer.hide() called (no-op).")

    def shutdown(self) -> None:
        logger.debug("NullAuraRenderer shut down.")
