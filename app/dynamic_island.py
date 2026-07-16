"""The Dynamic Island: a small, frameless floating pill overlay anchored to
the bottom-center of the primary screen, inspired by iPhone's Dynamic
Island.

Milestone 10 (reframed, 2026-07-16): this replaces the original "generic
settings screen wrapping config/" plan. Settings now live *inside* this
island (a button revealed in its expanded state, see `docs/DECISIONS.md`)
rather than in a separate always-visible panel, and this widget also
becomes Iris's new default-visible surface, retiring `app/main_window.py`'s
always-on debug window (Part D of this milestone).

This is Part A only: a static widget with two visual states
(`IslandState.COLLAPSED` / `IslandState.EXPANDED`) and the shape/color/
positioning to match. No activation wiring yet -- no global hotkey, no
wake-word hookup, no working settings button. See `set_state()`/`expand()`/
`collapse()`/`toggle()` for the public surface later parts will call into.

Deliberately independent of `aura/`: `AuraRenderer` communicates Iris's
*ambient state* via full-screen edge color (see `aura/renderer/base.py`),
which has no concept of layout, text, icons, or expand/collapse -- trying
to express the island through that interface would mean bolting arbitrary
widget content onto an interface designed for "set a color." See
`docs/DECISIONS.md` for the full reasoning; this module and `aura/` are two
independent renderers that `main.py` will own side by side.
"""

from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import QEasingCurve, QRect, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# --- Shape / sizing -----------------------------------------------------
# Collapsed: a small pill, fully rounded (radius == half the height), the
# "hidden/minimal by default" resting state.
COLLAPSED_WIDTH_PX = 150
COLLAPSED_HEIGHT_PX = 38

# Expanded: a larger rounded panel with room for a status line and (later,
# Part C) a real settings button. Radius is fixed rather than height/2 --
# a fully-stadium-shaped panel this wide would read as an oversized pill
# rather than a panel.
EXPANDED_WIDTH_PX = 380
EXPANDED_HEIGHT_PX = 130
EXPANDED_CORNER_RADIUS_PX = 28

# Gap between the widget's bottom edge and the screen's bottom edge.
BOTTOM_MARGIN_PX = 16

# --- Color -----------------------------------------------------------
# Near-black dark gray, per the user's explicit call (not pure black --
# pure black on an OLED-less/typical monitor reads as a dead flat cutout;
# a near-black gray keeps a little life in it while still reading as
# "black" at a glance).
BASE_R, BASE_G, BASE_B = 0x1A, 0x1A, 0x1A

# Frosted-glass approximation: this sandbox can't verify real OS-level
# backdrop blur (Windows Acrylic/DWM blur-behind is a real-hardware-only
# concern -- see docs/DECISIONS.md), so instead of literal background blur
# this fakes the "glass" read with (1) a subtle vertical gradient (a touch
# lighter at the top, darker at the bottom -- a top-lit sheen) and (2) a
# thin, low-alpha light rim stroke, both layered over a mostly-opaque fill
# so the shape stays clearly visible against any desktop content behind it.
FILL_ALPHA = 235
GRADIENT_TOP_LIFT = 38  # how much lighter the top of the gradient is vs BASE_*
RIM_COLOR = QColor(255, 255, 255, 70)
RIM_WIDTH_PX = 1.4

# --- State-change animation ---------------------------------------------
TRANSITION_MS = 220


class IslandState(Enum):
    COLLAPSED = "collapsed"
    EXPANDED = "expanded"


class DynamicIslandWidget(QWidget):
    """Frameless, translucent, always-on-top pill overlay.

    Unlike `aura/renderer`'s `_AuraOverlayWidget`/`_TargetBoxWidget`, this
    widget is *not* click-through (`WA_TransparentForMouseEvents` is
    intentionally omitted) -- it needs to receive real clicks once Part B/C
    wire up interaction. For now nothing is wired to those clicks yet.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._state = IslandState.COLLAPSED
        self._current_rect = self._target_rect(IslandState.COLLAPSED)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(TRANSITION_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)

        self.setGeometry(self._current_rect)
        logger.debug("DynamicIslandWidget constructed (state=%s).", self._state.value)

    # -- geometry -----------------------------------------------------

    def _target_rect(self, state: IslandState) -> QRect:
        """Compute the on-screen geometry for `state`, anchored to the
        bottom-center of the primary screen.

        Primary-monitor-only for now -- matches the existing Aura overlay's
        current limitation (see project memory/HANDOFF); multi-monitor
        support isn't in scope for this pass.
        """
        if state is IslandState.COLLAPSED:
            width, height = COLLAPSED_WIDTH_PX, COLLAPSED_HEIGHT_PX
        else:
            width, height = EXPANDED_WIDTH_PX, EXPANDED_HEIGHT_PX

        screen = QGuiApplication.primaryScreen()
        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        x = screen_geo.x() + (screen_geo.width() - width) // 2
        y = screen_geo.y() + screen_geo.height() - height - BOTTOM_MARGIN_PX
        return QRect(x, y, width, height)

    def _on_anim_value(self, rect: QRect) -> None:
        self._current_rect = rect
        self.setGeometry(rect)
        self.update()

    # -- public state API (later parts wire triggers to these) --------

    def set_state(self, state: IslandState) -> None:
        """Animate from the current geometry to `state`'s geometry."""
        if state is self._state and self._anim.state() != QVariantAnimation.State.Running:
            return
        self._state = state
        start_rect = QRect(self.geometry()) if self.isVisible() else self._current_rect
        end_rect = self._target_rect(state)
        self._anim.stop()
        self._anim.setStartValue(start_rect)
        self._anim.setEndValue(end_rect)
        self._anim.start()
        logger.debug("Island transitioning to state=%s.", state.value)

    def expand(self) -> None:
        self.set_state(IslandState.EXPANDED)

    def collapse(self) -> None:
        self.set_state(IslandState.COLLAPSED)

    def toggle(self) -> None:
        self.set_state(IslandState.COLLAPSED if self._state is IslandState.EXPANDED else IslandState.EXPANDED)

    @property
    def state(self) -> IslandState:
        return self._state

    def reposition(self) -> None:
        """Re-anchor to the current state's target rect without animating
        (e.g. after a screen/resolution change). Not wired to any signal
        yet -- available for a later part to call.
        """
        rect = self._target_rect(self._state)
        self._current_rect = rect
        self.setGeometry(rect)

    # -- painting -------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        radius = rect.height() / 2.0 if self._state is IslandState.COLLAPSED else EXPANDED_CORNER_RADIUS_PX
        # While mid-animation, shrink the radius proportionally so a
        # partially-expanded pill doesn't render an expanded panel's flat
        # corner radius on a still-small, near-pill-shaped rect (which
        # reads like a bug -- overly square corners on a small shape).
        radius = min(radius, rect.height() / 2.0)

        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(rect.width()), float(rect.height()), radius, radius)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(path)

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(
            0.0,
            QColor(
                min(BASE_R + GRADIENT_TOP_LIFT, 255),
                min(BASE_G + GRADIENT_TOP_LIFT, 255),
                min(BASE_B + GRADIENT_TOP_LIFT, 255),
                FILL_ALPHA,
            ),
        )
        gradient.setColorAt(1.0, QColor(BASE_R, BASE_G, BASE_B, FILL_ALPHA))
        painter.fillPath(path, gradient)

        pen = QPen(RIM_COLOR)
        pen.setWidthF(RIM_WIDTH_PX)
        painter.setPen(pen)
        painter.setClipping(False)
        painter.drawPath(path)

        if self._state is IslandState.EXPANDED:
            self._paint_expanded_content(painter, rect)

        painter.end()

    def _paint_expanded_content(self, painter: QPainter, rect: QRect) -> None:
        """Placeholder content for the expanded state: a title, a status
        line standing in for a future response/status area, and a
        decorative (non-interactive) settings glyph. Part C wires this
        icon to a real settings surface and replaces the status line with
        live content.
        """
        margin = 20

        painter.setPen(QColor(235, 235, 235, 235))
        title_font = painter.font()
        title_font.setPointSizeF(title_font.pointSizeF() + 3)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(margin, margin + 14, "Iris")

        painter.setPen(QColor(190, 190, 190, 200))
        body_font = painter.font()
        body_font.setBold(False)
        body_font.setPointSizeF(body_font.pointSizeF() - 3)
        painter.setFont(body_font)
        painter.drawText(margin, margin + 40, "Say the wake word, or ask anything.")

        # Decorative gear glyph, top-right corner -- not clickable yet.
        gear_cx = rect.width() - margin - 8
        gear_cy = margin + 6
        gear_r = 7
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 210, 210, 190))
        painter.drawEllipse(int(gear_cx - gear_r * 0.45), int(gear_cy - gear_r * 0.45), int(gear_r * 0.9), int(gear_r * 0.9))
        pen = QPen(QColor(210, 210, 210, 190))
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(gear_cx - gear_r), int(gear_cy - gear_r), int(gear_r * 2), int(gear_r * 2))
