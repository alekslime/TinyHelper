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

Visual model (2026-07-13 rewrite, replacing the flat-tint approach; widened
to a full-wheel pastel sweep later the same day):
the blurred edge-band shape is unchanged from the previous version (see
`_build_blurred_mask()`), but instead of re-tinting it to a single flat
color per frame, it's re-tinted with a `QConicalGradient` centered on the
screen: stops sweep through the *entire* hue wheel (+/- 180 degrees around
the current state's base hue -- i.e. all the way around, not a narrow
band), at low saturation/high value so every hue reads as pastel rather
than neon. The gradient's angle continuously rotates, so the effect is a
full-spectrum pastel wash smoothly circling the border. State is still
reflected -- the anchor hue (where the sweep's start/end seam sits) cross-
fades between states (see `_shortest_hue_delta()`) -- but since the sweep
already spans every hue, a state change now reads mainly as a shift in
*which hue is currently at a given angle* rather than a change in the
overall palette, which stays a continuous pastel rainbow throughout.

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

from PySide6.QtCore import QEasingCurve, QPointF, QRect, QRectF, Qt, QTimer, QVariantAnimation
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

# Milestone 7: how long the outline takes to morph between the full
# screen edge and a target box (either direction). Kept separate from
# TRANSITION_MS since these animate genuinely different things (color vs.
# geometry) and there's no reason they need matching durations -- picked
# slightly slower than the color fade since a moving/resizing shape reads
# better a bit more deliberately than an instant color swap does.
BOX_TRANSITION_MS = 600

# Milestone 7: the smallest a target box is allowed to be (in each
# dimension), in real screen pixels. Below this, the four blurred edge
# bands (each SEED_BAND_PX wide before blur) would overlap or degenerate
# into a single blob rather than a legible outline. Not yet tuned against
# a real display -- see docs/DECISIONS.md.
MIN_BOX_SIZE_PX = 2 * SEED_BAND_PX + 20


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


def _build_blurred_mask(canvas_width: int, canvas_height: int, target_rect: QRect) -> QImage:
    """Paint a solid white band along all four edges of `target_rect`
    (not necessarily the whole canvas -- see Milestone 7's
    `show_target_box`) and blur it with a real Gaussian blur
    (`QGraphicsBlurEffect`). The result is a shape-only mask (white,
    varying alpha) the size of the full canvas -- color is applied later,
    per frame, via `_tint_gradient()`, so this expensive part only has to
    run once per (canvas size, rect).

    When `target_rect` covers the whole canvas (Milestone 6's original,
    and Milestone 7's "no target box active" default), this reduces to
    exactly the original screen-edge-glow behavior.
    """
    seed = QImage(canvas_width, canvas_height, QImage.Format.Format_ARGB32_Premultiplied)
    seed.fill(0)
    painter = QPainter(seed)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 255))
    band = SEED_BAND_PX
    rx, ry, rw, rh = target_rect.x(), target_rect.y(), target_rect.width(), target_rect.height()
    # Four bands drawn INWARD from target_rect's own edges, not the
    # canvas's edges -- identical to the original code when target_rect
    # == the whole canvas.
    painter.drawRect(rx, ry, rw, band)
    painter.drawRect(rx, ry + rh - band, rw, band)
    painter.drawRect(rx, ry, band, rh)
    painter.drawRect(rx + rw - band, ry, band, rh)
    painter.end()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(seed))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(BLUR_RADIUS_PX)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    scene.setSceneRect(0, 0, canvas_width, canvas_height)

    blurred = QImage(canvas_width, canvas_height, QImage.Format.Format_ARGB32_Premultiplied)
    blurred.fill(0)
    result_painter = QPainter(blurred)
    canvas_rect = QRectF(0, 0, canvas_width, canvas_height)
    scene.render(result_painter, canvas_rect, canvas_rect)
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
        self._mask: QImage | None = None  # cached blurred shape, rebuilt on resize or target_rect change
        self._mask_cache_key: tuple[int, int, int, int, int, int] | None = None
        # Milestone 7: the rect the blurred edge bands currently trace, in
        # widget-local pixel coordinates. None until the first paint, at
        # which point it defaults to the full widget rect (screen-edge
        # glow, Milestone 6's original behavior). GlowAuraRenderer is
        # responsible for animating this via set_target_rect() as the
        # rect morphs between the full screen and a target box.
        self._target_rect: QRect | None = None

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

    def set_target_rect(self, rect: QRect) -> None:
        """Update the rect the blurred edge bands trace (Milestone 7).
        Invalidates the cached mask so it's rebuilt against the new rect
        on next paint -- same lazy-rebuild pattern as a resize.
        """
        self._target_rect = rect
        self._mask = None
        self._mask_cache_key = None
        self.update()

    def stop(self) -> None:
        self._anim_timer.stop()

    def _ensure_mask(self) -> QImage | None:
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return None
        rect = self._target_rect if self._target_rect is not None else QRect(0, 0, w, h)
        cache_key = (w, h, rect.x(), rect.y(), rect.width(), rect.height())
        if self._mask is None or self._mask_cache_key != cache_key:
            logger.debug("Rebuilding Aura blur mask for size %sx%s, rect=%s.", w, h, rect)
            self._mask = _build_blurred_mask(w, h, rect)
            self._mask_cache_key = cache_key
        return self._mask

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        # Invalidate the cached mask; it'll be rebuilt lazily on next paint.
        # Deliberately does NOT reset self._target_rect -- a resize while a
        # target box is active (unlikely for a full-screen overlay, but
        # possible on a display/resolution change) should keep tracing the
        # same rect, not silently reset to the full screen edge.
        self._mask = None
        self._mask_cache_key = None
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
        # Milestone 7: geometry side of the aura, orthogonal to the color
        # animation above. `_screen_rect` is the "home" rect (full screen
        # edge) computed once in initialize(); `_rect_animation` morphs
        # `_current_rect` between that and whatever target box is active.
        self._screen_rect: QRect | None = None
        self._current_rect: QRect | None = None
        self._rect_animation: QVariantAnimation | None = None

    def initialize(self) -> None:
        self._widget = _AuraOverlayWidget()

        # Span the full virtual desktop (the union of every connected
        # screen's geometry), NOT just the primary screen. This has to
        # match `mss`'s monitor_index=0 combined-virtual-screen geometry
        # (what `vision.capture()` actually captures and `locate()`'s
        # pixel math is computed against, per ScreenCapture.monitor_geometry)
        # -- previously this was primaryScreen()-only, which meant a
        # target box computed correctly for a non-primary monitor could
        # never actually be drawn there: the overlay widget itself didn't
        # extend that far, so show_target_box()'s own clamping silently
        # forced it back onto the primary monitor instead. See the bug
        # report where "point to X" resolved correctly but never visibly
        # pointed at anything on a second monitor.
        primary = QGuiApplication.primaryScreen()
        geometry: QRect | None = None
        if primary is not None:
            # virtualGeometry() is the union of this screen's virtual
            # siblings -- i.e. the same combined virtual-desktop rect mss
            # calls monitor index 0. Falls back to a manual union of
            # QGuiApplication.screens() if virtualGeometry() isn't
            # available or returns something degenerate.
            vg = primary.virtualGeometry()
            if vg.isValid() and vg.width() > 0 and vg.height() > 0:
                geometry = QRect(vg)

        if geometry is None:
            screens = QGuiApplication.screens()
            if screens:
                union_rect = QRect()
                for s in screens:
                    union_rect = union_rect.united(s.geometry())
                if union_rect.width() > 0 and union_rect.height() > 0:
                    geometry = union_rect

        if geometry is not None:
            self._widget.setGeometry(geometry)
        else:
            logger.warning("No screen geometry detected — Aura overlay using a fallback size.")
            self._widget.resize(1920, 1080)

        self._widget.set_anchor_hue(self._current_hue)

        # Milestone 7: the "home" rect a target box always morphs back to.
        # Falls back to the same 1920x1080 default used above when no
        # primary screen is detected, so the two never disagree.
        self._screen_rect = QRect(geometry) if geometry is not None else QRect(0, 0, 1920, 1080)
        self._current_rect = QRect(self._screen_rect)

        self._animation = QVariantAnimation()
        self._animation.setDuration(TRANSITION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_animation_value_changed)

        self._rect_animation = QVariantAnimation()
        self._rect_animation.setDuration(BOX_TRANSITION_MS)
        self._rect_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rect_animation.valueChanged.connect(self._on_rect_animation_value_changed)

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

    def _on_rect_animation_value_changed(self, value: QRect) -> None:
        # `value` arrives as a QRect (or QRectF, depending on Qt's
        # interpolation of the QVariant) -- normalize to QRect since
        # `_AuraOverlayWidget.set_target_rect` expects integer pixel
        # coordinates.
        rect = value if isinstance(value, QRect) else value.toRect()
        self._current_rect = rect
        if self._widget is not None:
            self._widget.set_target_rect(rect)

    def _clamp_target_rect(self, x: int, y: int, w: int, h: int) -> QRect:
        """Clamp an untrusted (x, y, w, h) -- e.g. straight from the
        vision model's `locate()` output -- to a legal rect fully inside
        the screen, with each dimension at least `MIN_BOX_SIZE_PX`. See
        `AuraRenderer.show_target_box`'s docstring for why this can't
        just trust the caller.
        """
        screen = self._screen_rect if self._screen_rect is not None else QRect(0, 0, 1920, 1080)

        width = max(int(w), MIN_BOX_SIZE_PX)
        height = max(int(h), MIN_BOX_SIZE_PX)
        width = min(width, screen.width())
        height = min(height, screen.height())

        # Clamp the origin so the whole rect stays on-screen, not just its
        # top-left corner -- an (x, y) near the bottom-right edge combined
        # with a large w/h would otherwise hang off the screen.
        max_x = screen.left() + screen.width() - width
        max_y = screen.top() + screen.height() - height
        left = max(screen.left(), min(int(x), max_x))
        top = max(screen.top(), min(int(y), max_y))

        return QRect(left, top, width, height)

    def _animate_rect_to(self, target: QRect) -> None:
        if self._widget is None:
            return

        if self._rect_animation is None:
            # show_target_box()/clear_target_box() called before
            # initialize() -- shouldn't happen via AuraController, but
            # degrade to an instant jump rather than crash, same pattern
            # as set_state()'s equivalent guard.
            self._current_rect = QRect(target)
            self._widget.set_target_rect(target)
            return

        start = self._current_rect if self._current_rect is not None else target
        self._rect_animation.stop()
        self._rect_animation.setStartValue(QRect(start))
        self._rect_animation.setEndValue(QRect(target))
        self._rect_animation.start()

    def show_target_box(self, x: int, y: int, w: int, h: int) -> None:
        target = self._clamp_target_rect(x, y, w, h)
        self._animate_rect_to(target)

    def clear_target_box(self) -> None:
        home = self._screen_rect if self._screen_rect is not None else QRect(0, 0, 1920, 1080)
        self._animate_rect_to(home)

    def show(self) -> None:
        if self._widget is not None:
            self._widget.show()

    def hide(self) -> None:
        if self._widget is not None:
            self._widget.hide()

    def shutdown(self) -> None:
        if self._animation is not None:
            self._animation.stop()
        if self._rect_animation is not None:
            self._rect_animation.stop()
        if self._widget is not None:
            self._widget.stop()
            self._widget.close()
            self._widget = None