"""A real, visible `AuraRenderer`: a soft ambient glow around the screen
edges, color-coded per `AuraState`, with smooth cross-fade transitions.

Replaces `NullAuraRenderer` as Iris's default renderer (Milestone 6). Built
as a frameless, click-through, always-on-top top-level widget painted with
QPainter gradients rather than a literal custom GPU shader pipeline --
see docs/DECISIONS.md for why this still satisfies the roadmap's "GPU-
rendered ambient edge glow" goal without a much heavier OpenGL/QML
dependency.

Design constraints from docs/ROADMAP.md, honored here:
    - State-based color transitions (idle/listening/thinking/waiting/error)
    - Smooth fade in/out, no sharp edges
    - No neon/pulsing -- colors cross-fade once per state change and then
      sit still; nothing animates continuously while idle in a state.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from aura.renderer.base import AuraRenderer
from aura.states import DEFAULT_STATE_COLORS, AuraState

logger = logging.getLogger(__name__)

# How far the glow extends inward from each screen edge, in pixels.
GLOW_DEPTH = 140

# Alpha (0-255) of the glow right at the screen edge; fades to 0 by GLOW_DEPTH in.
GLOW_EDGE_ALPHA = 110

# How long a state-to-state color cross-fade takes.
TRANSITION_MS = 350


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

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Additive blending: overlapping edge/corner gradients brighten
        # together instead of one overwriting another, which is what makes
        # the corners look like one continuous glow rather than four
        # separate rectangles with visible seams.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.setPen(Qt.PenStyle.NoPen)

        w, h = self.width(), self.height()
        depth = GLOW_DEPTH

        def edge_color(alpha: int) -> QColor:
            c = QColor(self._color)
            c.setAlpha(alpha)
            return c

        edge_bands = [
            (QRectF(0, 0, w, depth), QLinearGradient(0, 0, 0, depth)),  # top
            (QRectF(0, h - depth, w, depth), QLinearGradient(0, h, 0, h - depth)),  # bottom
            (QRectF(0, 0, depth, h), QLinearGradient(0, 0, depth, 0)),  # left
            (QRectF(w - depth, 0, depth, h), QLinearGradient(w, 0, w - depth, 0)),  # right
        ]
        for rect, gradient in edge_bands:
            gradient.setColorAt(0.0, edge_color(GLOW_EDGE_ALPHA))
            gradient.setColorAt(1.0, edge_color(0))
            painter.fillRect(rect, gradient)

        # Radial patches at each corner smooth the seam where two edge
        # bands would otherwise meet at a visible right angle.
        for cx, cy in ((0, 0), (w, 0), (0, h), (w, h)):
            radial = QRadialGradient(cx, cy, depth)
            radial.setColorAt(0.0, edge_color(GLOW_EDGE_ALPHA))
            radial.setColorAt(1.0, edge_color(0))
            painter.setBrush(QBrush(radial))
            painter.drawRect(QRectF(cx - depth, cy - depth, depth * 2, depth * 2))

        painter.end()


class GlowAuraRenderer(AuraRenderer):
    """Owns the overlay widget and animates color transitions between states.

    Stateless about *why* a state changed -- same separation of concerns as
    `NullAuraRenderer`, just with actual pixels now.
    """

    def __init__(self) -> None:
        self._widget: _AuraOverlayWidget | None = None
        self._animation: QVariantAnimation | None = None
        self._current_color: QColor = QColor(*DEFAULT_STATE_COLORS[AuraState.IDLE])

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
        target_color = QColor(*target_rgb)

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
            self._widget.close()
            self._widget = None
