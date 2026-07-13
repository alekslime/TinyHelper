"""A real, visible `AuraRenderer`: a soft ambient glow around the screen
edges, color-coded per `AuraState`, built from an actual Gaussian blur,
tinted with a slowly-rotating multicolor gradient (rather than a flat
color) and cross-faded smoothly between states.

Replaces `NullAuraRenderer` as Iris's default renderer (Milestone 6). Built
as a frameless, click-through, always-on-top top-level widget painted with
QPainter/`QGraphicsBlurEffect` rather than a literal custom GPU shader
pipeline -- see docs/DECISIONS.md for why this still satisfies the
roadmap's "GPU-rendered ambient edge glow" goal without a much heavier
OpenGL/QML dependency.

Visual model (2026-07-13 rewrite, replacing the flat-tint approach):
the blurred edge-band shape is unchanged from the previous version (see
`_build_blurred_mask()`), but instead of re-tinting it to a single flat
color per frame, it's re-tinted with a `QConicalGradient` centered on the
screen: a handful of color stops orbit the current state's base hue
(spread +/- `GRADIENT_HUE_SPREAD_DEG` degrees, wrapping back to the base
hue so the loop has no seam), and the gradient's angle slowly rotates
over time. The net effect is a multicolor glow that continuously drifts
through nearby hues around the border, while still visibly anchored to
whatever color the current `AuraState` maps to -- state changes cross-fade
the *anchor* hue (see `_shortest_hue_delta()`), the rotation and spread
keep animating underneath that the whole time.

Design constraints from docs/ROADMAP.md, honored here:
    - State-based color transitions (idle/listening/thinking/waiting/error)
    - Smooth fade in/out, no sharp/harsh edges (Gaussian blur, unchanged)
    - A slow, subtle continuous animation (not a sharp flashing pulse) --
      previously a breathing alpha pulse, now a rotating multicolor
      gradient; see docs/DECISIONS.md for the history of this element.
"""

from __future__ import annotations

import logging
import math
import time

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QConicalGradient, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene, QWidget

from aura.renderer.base import AuraRenderer
from aura.states import DEFAULT_STATE_COLORS, AuraState

logger = logging.getLogger(__name__)

# Width of the solid seed band painted along each edge before blurring.
# This is the "shape" that then gets blurred into a glow -- not the final
# visible width, which ends up wider once blur spreads it.
SEED_BAND_PX = 18  # was 55; cut down, was eating too much of the screen

# Qt blur radius (roughly, the blur's standard deviation in pixels). This
# is what actually determines how far and how softly the glow spreads --
# and was the main reason the glow reached so far inward before.
BLUR_RADIUS_PX = 38  # was 90; cut down alongside SEED_BAND_PX

# Peak alpha (0-255) of the tint applied to the blurred shape.
PEAK_ALPHA = 235

# --- Multicolor gradient: a QConicalGradient centered on the screen whose
# stops orbit the current state's base hue, continuously rotating so the
# border reads as alive/flowing rather than a flat static tint.
GRADIENT_STOPS = 13          # more stops = smoother hue interpolation
GRADIENT_HUE_SPREAD_DEG = 45  # how far stops swing from the anchor hue
ROTATION_PERIOD_S = 9.0       # seconds for one full 360-degree rotation
GRADIENT_FPS = 30
GRADIENT_SAT = 235
GRADIENT_VAL = 245

# How long a state-to-state hue cross-fade takes.
TRANSITION_MS = 500


def _shortest_hue_delta(start_deg: float, end_deg: float) -> float:
    """Return the signed delta (in degrees) from `start_deg` to `end_deg`
    that takes the shorter way around the color wheel, so animating a hue
    never spins the "long way" around 360 degrees.
    """
    delta = (end_deg - start_deg) % 360.0
    if delta > 180.0:
        delta -= 360.0
    return delta


def _gradient_colors(anchor_hue_deg: float, alpha: int) -> list[QColor]:
    """Build the list of `GRADIENT_STOPS` colors used for one frame's
    conical gradient: hues sweep from `anchor_hue_deg + spread` down to
    `anchor_hue_deg - spread` and back up to `anchor_hue_deg + spread`
    again (a cosine wave over stop position), so the first and last stop
    match exactly -- required for a seamless loop on a gradient that wraps
    around a full circle.
    """
    colors: list[QColor] = []
    for i in range(GRADIENT_STOPS):
        t = i / (GRADIENT_STOPS - 1)
        offset = GRADIENT_HUE_SPREAD_DEG * math.cos(2 * math.pi * t)
        hue = (anchor_hue_deg + offset) % 360.0
        color = QColor()
        color.setHsv(int(hue), GRADIENT_SAT, GRADIENT_VAL, alpha)
        colors.append(color)
    return colors


def _build_blurred_mask(width: int, height: int) -> QImage:
    """Paint a solid white band along all four edges and blur it with a
    real Gaussian blur (`QGraphicsBlurEffect`). The result is a shape-only
    mask (white, varying alpha) -- color is applied later, per frame, via
    `_tint_gradient()`, so this expensive part only has to run once per
    size.
    """
    seed = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    seed.fill(0)
    painter = QPainter(seed)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 255))
    band = SEED_BAND_PX
    painter.drawRect(0, 0, width, band)
    painter.drawRect(0, height - band, width, band)
    painter.drawRect(0, 0, band, height)
    painter.drawRect(width - band, 0, band, height)
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


def _tint_gradient(mask: QImage, anchor_hue_deg: float, rotation_deg: float, alpha: int) -> QImage:
    """Recolor a blurred white mask with a rotating multicolor
    `QConicalGradient` centered on the mask, keeping the mask's own alpha
    shape (`CompositionMode_SourceIn`). Cheap relative to
    `_build_blurred_mask` -- this is the only per-frame work.
    """
    tinted = QImage(mask)
    painter = QPainter(tinted)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)

    center = QPointF(tinted.width() / 2.0, tinted.height() / 2.0)
    gradient = QConicalGradient(center, rotation_deg)
    colors = _gradient_colors(anchor_hue_deg, alpha)
    for i, color in enumerate(colors):
        gradient.setColorAt(i / (len(colors) - 1), color)

    painter.fillRect(tinted.rect(), gradient)
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
        self._anchor_hue = 0.0  # current state's base hue, 0-360 (animated on state change)
        self._rotation = 0.0    # current gradient rotation angle, degrees
        self._mask: QImage | None = None  # cached blurred shape, rebuilt on resize
        self._mask_size: tuple[int, int] | None = None

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(int(1000 / GRADIENT_FPS))
        self._anim_timer.timeout.connect(self._tick)
        self._anim_start = time.monotonic()
        self._anim_timer.start()

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._anim_start
        phase = (elapsed % ROTATION_PERIOD_S) / ROTATION_PERIOD_S
        self._rotation = phase * 360.0
        self.update()

    def set_anchor_hue(self, hue_deg: float) -> None:
        self._anchor_hue = hue_deg % 360.0
        self.update()

    def stop(self) -> None:
        self._anim_timer.stop()

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

        tinted = _tint_gradient(mask, self._anchor_hue, self._rotation, PEAK_ALPHA)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawImage(0, 0, tinted)
        painter.end()


def _base_hue(state: AuraState) -> float:
    """The anchor hue (0-360 degrees) a given `AuraState` maps to, derived
    from its entry in `DEFAULT_STATE_COLORS`.
    """
    rgb = DEFAULT_STATE_COLORS.get(state, DEFAULT_STATE_COLORS[AuraState.IDLE])
    hue = QColor(*rgb).hue()  # -1 for achromatic (grey); none of the defaults are
    return float(hue) if hue >= 0 else 0.0


class GlowAuraRenderer(AuraRenderer):
    """Owns the overlay widget and animates anchor-hue transitions between
    states.

    Stateless about *why* a state changed -- same separation of concerns as
    `NullAuraRenderer`, just with actual pixels now.
    """

    def __init__(self) -> None:
        self._widget: _AuraOverlayWidget | None = None
        self._animation: QVariantAnimation | None = None
        self._current_hue: float = _base_hue(AuraState.IDLE)

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

        self._widget.set_anchor_hue(self._current_hue)

        self._animation = QVariantAnimation()
        self._animation.setDuration(TRANSITION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_animation_value_changed)

        logger.debug("GlowAuraRenderer initialized (geometry=%s).", geometry)

    def _on_animation_value_changed(self, value: float) -> None:
        self._current_hue = float(value) % 360.0
        if self._widget is not None:
            self._widget.set_anchor_hue(self._current_hue)

    def set_state(self, state: AuraState) -> None:
        target_hue = _base_hue(state)

        if self._animation is None:
            # set_state called before initialize() — shouldn't happen via
            # AuraController, but degrade to an instant hue set rather
            # than crash if it ever does.
            self._current_hue = target_hue
            if self._widget is not None:
                self._widget.set_anchor_hue(target_hue)
            return

        # Animate via a delta from the current hue, taking the shorter way
        # around the color wheel, rather than animating start->end hue
        # values directly (which would wrap the "long way" whenever the
        # target hue is numerically smaller, e.g. 260 -> 45).
        delta = _shortest_hue_delta(self._current_hue, target_hue)
        self._animation.stop()
        self._animation.setStartValue(self._current_hue)
        self._animation.setEndValue(self._current_hue + delta)
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