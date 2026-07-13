"""A real, visible `AuraRenderer`: a soft ambient glow around the screen
edges, color-coded per `AuraState`, built from an actual Gaussian blur
rather than hand-authored gradient stops, with smooth cross-fade
transitions between states and a slow, continuous "breathing" pulse.

Replaces `NullAuraRenderer` as Iris's default renderer (Milestone 6). Built
as a frameless, click-through, always-on-top top-level widget painted with
QPainter/`QGraphicsBlurEffect` rather than a literal custom GPU shader
pipeline -- see docs/DECISIONS.md for why this still satisfies the
roadmap's "GPU-rendered ambient edge glow" goal without a much heavier
OpenGL/QML dependency.

Visual model (2026-07-13 rewrite, corner-weighted): most of the visible
glow now lives in soft radial blobs seeded at the four corners, connected
by a thin seed band along each edge -- rather than a uniform band running
the full length of every edge. The seed shape (corner blobs + thin edge
band) is still blurred with Qt's `QGraphicsBlurEffect`, a real Gaussian
blur, not a manually tuned multi-stop gradient. The blurred shape (a
`QImage`) is cached and only rebuilt on resize; per-frame work is just
re-tinting that cached shape to the current color/brightness, which is
cheap.

Design constraints from docs/ROADMAP.md, honored here:
    - State-based color transitions (idle/listening/thinking/waiting/error)
    - Smooth fade in/out, no sharp/harsh edges (now a true Gaussian blur)
    - A slow, subtle continuous breathing pulse (not a sharp flashing
      pulse) -- intentionally revises the earlier "no pulsing" decision
      after real-hardware feedback that the static version looked flat;
      see docs/DECISIONS.md.
"""

from __future__ import annotations

import logging
import math
import time

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene, QWidget

from aura.renderer.base import AuraRenderer
from aura.states import DEFAULT_STATE_COLORS, AuraState

logger = logging.getLogger(__name__)

# Width of the thin seed band painted along each edge before blurring.
# This is just a faint connecting line between corners now -- most of the
# visible glow comes from the corner blobs below, not this band.
EDGE_BAND_PX = 15  # was SEED_BAND_PX = 18; kept thin on purpose

# Pre-blur radius of the soft radial blob seeded at each corner. This is
# where most of the glow actually lives -- the corner-weighted look.
CORNER_BLOB_PX = 130

# Qt blur radius (roughly, the blur's standard deviation in pixels). This
# is what actually determines how far and how softly the glow spreads.
# Kept lower than the old uniform-band version so the result reads as
# thin rather than a thick wash along each edge.
BLUR_RADIUS_PX = 26  # was 38

# Peak alpha (0-255) of the tint applied to the blurred shape, before the
# breathing multiplier is applied.
PEAK_ALPHA = 235

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


def _build_blurred_mask(width: int, height: int) -> QImage:
    """Paint a thin white band along all four edges plus a soft radial
    blob at each corner, then blur it with a real Gaussian blur
    (`QGraphicsBlurEffect`). The result is a shape-only mask (white,
    varying alpha) -- color is applied later, per frame, via `_tint()`,
    so this expensive part only has to run once per size.

    Corner-weighted on purpose: the blobs carry most of the visible glow,
    the edge band is just a thin connecting line, not a second glow
    source competing with it.
    """
    seed = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    seed.fill(0)
    painter = QPainter(seed)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    painter.setBrush(QColor(255, 255, 255, 255))
    band = EDGE_BAND_PX
    painter.drawRect(0, 0, width, band)
    painter.drawRect(0, height - band, width, band)
    painter.drawRect(0, 0, band, height)
    painter.drawRect(width - band, 0, band, height)

    for cx, cy in ((0, 0), (width, 0), (0, height), (width, height)):
        gradient = QRadialGradient(cx, cy, CORNER_BLOB_PX)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 255))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(cx, cy), CORNER_BLOB_PX, CORNER_BLOB_PX)
    painter.end()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(seed))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(BLUR_RADIUS_PX)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    scene.setSceneRect(0, 0, width, height)

    blurred = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    blurred.fill(0)
    result_painter = QPainter(blurred)
    scene.render(result_painter, QRectF(0, 0, width, height), QRectF(0, 0, width, height))
    result_painter.end()
    return blurred


def _tint(mask: QImage, color: QColor, alpha: int) -> QImage:
    """Recolor a blurred white mask to `color` at `alpha`, keeping the
    mask's own alpha shape. Cheap relative to `_build_blurred_mask` --
    this is the only per-frame work.
    """
    tinted = QImage(mask)
    painter = QPainter(tinted)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    tint_color = QColor(color)
    tint_color.setAlpha(max(0, min(255, alpha)))
    painter.fillRect(tinted.rect(), tint_color)
    painter.end()
    return tinted


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
        self._mask: QImage | None = None  # cached blurred shape, rebuilt on resize
        self._mask_size: tuple[int, int] | None = None

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

    def _ensure_mask(self) -> QImage | None:
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return None
        if self._mask is None or self._mask_size != (w, h):
            logger.debug("Rebuilding Aura blur mask for size %sx%s.", w, h)
            self._mask = _build_blurred_mask(w, h)
            self._mask_size = (w, h)
        return self._mask

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        # Invalidate the cached mask; it'll be rebuilt lazily on next paint.
        self._mask = None
        self._mask_size = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        mask = self._ensure_mask()
        if mask is None:
            return

        peak = int(PEAK_ALPHA * self._breath)
        tinted = _tint(mask, self._color, peak)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawImage(0, 0, tinted)
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
