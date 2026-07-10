"""A real, visible `AuraRenderer`: a thin, saturated neon border that hugs
the screen edges (bias-lighting style), color-coded per `AuraState`, with
smooth cross-fade transitions between states and a slow, continuous
"breathing" pulse so it doesn't read as flat/static.

Replaces `NullAuraRenderer` as Iris's default renderer (Milestone 6). Built
as a frameless, click-through, always-on-top top-level widget painted with
QPainter gradients rather than a literal custom GPU shader pipeline --
see docs/DECISIONS.md for why this still satisfies the roadmap's "GPU-
rendered ambient edge glow" goal without a much heavier OpenGL/QML
dependency.

Visual model: each edge is one continuous multi-stop gradient (not a
separate "core" rectangle stacked on a separate "bloom" rectangle, which
produced a visible seam) that feathers in from fully transparent at the
true screen edge, up to peak brightness a short distance in, then decays
smoothly back to transparent by `GLOW_DEPTH`. A slow sine-driven
"breath" scales that peak brightness up and down continuously so the
border has a sense of life instead of sitting at one flat opacity.

Design constraints from docs/ROADMAP.md, honored here:
    - State-based color transitions (idle/listening/thinking/waiting/error)
    - Smooth fade in/out, no sharp/harsh edges (12px feather at the seam)
    - A slow, subtle continuous breathing pulse (not a sharp flashing
      pulse) -- intentionally revises the earlier "no pulsing" decision
      after real-hardware feedback that the static version looked flat;
      see docs/DECISIONS.md.
"""

from __future__ import annotations

import logging
import math
import time

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from aura.renderer.base import AuraRenderer
from aura.states import DEFAULT_STATE_COLORS, AuraState

logger = logging.getLogger(__name__)

# How far the glow extends inward from each screen edge, in pixels, before
# fully fading to transparent.
GLOW_DEPTH = 70  # confirmed via pixel comparison against user's reference
# image (2026-07-11) -- the 105px/200px experiments were the wrong
# direction; this original size is what the user actually wants.

# How far in from the true edge the brightness peaks. Below this, alpha
# feathers up from 0 (at the edge) to the peak -- this is what removes
# the hard/flat line-against-nothing look at the screen boundary itself.
FEATHER_PX = 12  # reverted alongside GLOW_DEPTH, same reasoning

# Peak alpha (0-255) at the brightest point of the gradient (at
# FEATHER_PX in from the edge), before the breathing multiplier is
# applied.
PEAK_ALPHA = 225

# --- Breathing pulse: a slow, continuous sine wave scaling peak alpha up
# and down so the border reads as alive rather than a flat static line.
# Subtle by design -- this is meant to feel like breathing, not blinking.
BREATH_PERIOD_S = 4.2
BREATH_MIN = 0.72  # multiplier on PEAK_ALPHA at the dimmest point
BREATH_MAX = 1.0   # multiplier on PEAK_ALPHA at the brightest point
BREATH_FPS = 30

# How long a state-to-state color cross-fade takes.
TRANSITION_MS = 350


def _vivid(color: QColor) -> QColor:
    """Boost a state color to near-full saturation/brightness so it reads
    as a punchy neon tone rather than the softer flat colors used
    elsewhere in the app's palette (e.g. buttons, text).
    """
    h, s, v, a = color.getHsv()
    vivid = QColor()
    vivid.setHsv(h, max(s, 235), max(v, 245), a)
    return vivid


class _AuraOverlayWidget(QWidget):
    """The actual painted surface. Frameless, transparent, click-through,
    always-on-top -- so it sits over everything else on screen without
    ever intercepting a click or keystroke meant for another app.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._color = QColor(66, 133, 244)
        self._breath = 1.0  # current breathing multiplier, 0..1

        self._breath_timer = QTimer(self)
        self._breath_timer.setInterval(int(1000 / BREATH_FPS))
        self._breath_timer.timeout.connect(self._tick_breath)
        self._breath_start = time.monotonic()
        self._breath_timer.start()

    def _tick_breath(self) -> None:
        elapsed = time.monotonic() - self._breath_start
        phase = (elapsed % BREATH_PERIOD_S) / BREATH_PERIOD_S
        # 0..1 sine, smooth continuous loop -- no snap at the wraparound.
        wave = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
        self._breath = BREATH_MIN + (BREATH_MAX - BREATH_MIN) * wave
        self.update()

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def stop(self) -> None:
        self._breath_timer.stop()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Additive blending: overlapping edge/corner gradients brighten
        # together instead of one overwriting another, which is what makes
        # the corners look like one continuous strip rather than four
        # separate rectangles with visible seams.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.setPen(Qt.PenStyle.NoPen)

        w, h = self.width(), self.height()
        depth = GLOW_DEPTH
        peak = int(PEAK_ALPHA * self._breath)
        feather_stop = FEATHER_PX / depth if depth else 0.0

        def edge_color(alpha: int) -> QColor:
            c = QColor(self._color)
            c.setAlpha(max(0, min(255, alpha)))
            return c

        def apply_stops(gradient: QLinearGradient | QRadialGradient) -> None:
            # One continuous curve per edge: transparent at the true
            # screen edge, feathering up to peak brightness by
            # FEATHER_PX in, then decaying smoothly back to transparent
            # by `depth`. Using several intermediate stops (rather than
            # a 2-stop linear ramp) rounds the decay so it reads as a
            # soft glow instead of a harsh straight-line fade.
            gradient.setColorAt(0.0, edge_color(0))
            gradient.setColorAt(min(feather_stop, 0.99), edge_color(peak))
            remaining = 1.0 - feather_stop
            if remaining > 0:
                gradient.setColorAt(feather_stop + remaining * 0.35, edge_color(int(peak * 0.55)))
                gradient.setColorAt(feather_stop + remaining * 0.7, edge_color(int(peak * 0.18)))
            gradient.setColorAt(1.0, edge_color(0))

        edge_bands = [
            (QRectF(0, 0, w, depth), QLinearGradient(0, 0, 0, depth)),  # top
            (QRectF(0, h - depth, w, depth), QLinearGradient(0, h, 0, h - depth)),  # bottom
            (QRectF(0, 0, depth, h), QLinearGradient(0, 0, depth, 0)),  # left
            (QRectF(w - depth, 0, depth, h), QLinearGradient(w, 0, w - depth, 0)),  # right
        ]
        for rect, gradient in edge_bands:
            apply_stops(gradient)
            painter.fillRect(rect, gradient)

        # Radial patches at each corner smooth the seam where two edge
        # bands would otherwise meet at a visible right angle -- same
        # feathered profile, just radial instead of linear.
        for cx, cy in ((0, 0), (w, 0), (0, h), (w, h)):
            radial = QRadialGradient(cx, cy, depth)
            apply_stops(radial)
            painter.fillRect(QRectF(cx - depth, cy - depth, depth * 2, depth * 2), QBrush(radial))

        painter.end()


class GlowAuraRenderer(AuraRenderer):
    """Owns the overlay widget and animates color transitions between states.

    Stateless about *why* a state changed -- same separation of concerns as
    `NullAuraRenderer`, just with actual pixels now.
    """

    def __init__(self) -> None:
        self._widget: _AuraOverlayWidget | None = None
        self._animation: QVariantAnimation | None = None
        self._current_color: QColor = _vivid(QColor(*DEFAULT_STATE_COLORS[AuraState.IDLE]))

    def initialize(self) -> None:
        self._widget = _AuraOverlayWidget()

        screen = QGuiApplication.primaryScreen()
        # NOTE: primary screen only -- a real multi-monitor glow spanning
        # every display's combined virtual geometry is a known follow-up,
        # not implemented yet. See docs/TODO.md.
        geometry = screen.geometry() if screen is not None else None
        if geometry is not None:
            self._widget.setGeometry(geometry)
        else:
            logger.warning("No primary screen detected — Aura overlay using a fallback size.")
            self._widget.resize(1920, 1080)

        self._widget.set_color(self._current_color)

        self._animation = QVariantAnimation()
        self._animation.setDuration(TRANSITION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_animation_value_changed)

        logger.debug("GlowAuraRenderer initialized (geometry=%s).", geometry)

    def _on_animation_value_changed(self, value: QColor) -> None:
        self._current_color = value
        if self._widget is not None:
            self._widget.set_color(value)

    def set_state(self, state: AuraState) -> None:
        target_rgb = DEFAULT_STATE_COLORS.get(state, DEFAULT_STATE_COLORS[AuraState.IDLE])
        target_color = _vivid(QColor(*target_rgb))

        if self._animation is None:
            # set_state called before initialize() — shouldn't happen via
            # AuraController, but degrade to an instant color set rather
            # than crash if it ever does.
            self._current_color = target_color
            if self._widget is not None:
                self._widget.set_color(target_color)
            return

        self._animation.stop()
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(target_color)
        self._animation.start()

    def show(self) -> None:
        if self._widget is not None:
            self._widget.show()

    def hide(self) -> None:
        if self._widget is not None:
            self._widget.hide()

    def shutdown(self) -> None:
        if self._animation is not None:
            self._animation.stop()
        if self._widget is not None:
            self._widget.stop()
            self._widget.close()
            self._widget = None
