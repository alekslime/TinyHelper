"""Iris application entry point.

Responsible only for wiring things together:
    1. Load configuration.
    2. Set up logging.
    3. Construct the (placeholder, no-op) Aura controller.
    4. Construct voice activation (microphone + wake word detection +
       speech-to-text) and bridge its events onto the Qt main thread.
    5. Construct the local LLM engine and bridge its results onto the Qt
       main thread.
    6. If enabled, construct screen capture + a vision model, so each
       query can be augmented with a caption of the current screen.
    7. Launch the Qt application and a minimal window.

No feature logic belongs here — this file should stay small forever.
"""

from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtWidgets import QApplication

from app.llm_bridge import LLMResponseBridge
from app.locate_bridge import LocateResultBridge
from app.main_window import MainWindow
from app.transcript_bridge import TranscriptBridge
from app.vision_locate_bridge import VisionLocateBridge
from app.wake_word_bridge import WakeWordBridge
from aura.controller import AuraController
from aura.renderer.glow_renderer import GlowAuraRenderer
from aura.renderer.null_renderer import NullAuraRenderer
from aura.states import AuraState
from config.settings import get_settings
from utils.logger import setup_logging

logger = logging.getLogger(__name__)

# Milestone 7 (Part B.3, revised): a locate() box covering this much of the
# screenshot's area (as a percent -- w*h where w/h are themselves already
# 0-100 percentages) or more is treated as a degenerate "found the whole
# screen" non-answer, same bucket as a zero-area box. 80% is deliberately
# generous -- a real, legitimately large UI element (e.g. a maximized
# window's whole client area) could plausibly hit 60-70%, but "the entire
# multi-monitor virtual desktop" (100%) or anything close to it is never a
# genuine single-element answer. Not yet tuned against real-world results
# beyond the one incident that prompted it -- see docs/DECISIONS.md.
LOCATE_MAX_BOX_AREA_PCT = 80

# `voice.service` depends on the optional "speech" extras (openwakeword,
# sounddevice, faster-whisper) — see pyproject.toml and docs/DECISIONS.md.
# Import it defensively so Iris still launches with just the core
# dependencies installed; voice activation is simply unavailable in that case.
try:
    from voice.service import VoiceActivationService

    _VOICE_AVAILABLE = True
except ImportError:
    VoiceActivationService = None  # type: ignore[assignment,misc]
    _VOICE_AVAILABLE = False

# `llm.engine` depends on the optional "llm" extra (llama-cpp-python) — see
# pyproject.toml and docs/DECISIONS.md. Same defensive-import treatment as
# voice, above — Iris still launches without it, just without generated
# responses.
try:
    from llm.engine import LLMEngine

    _LLM_AVAILABLE = True
except ImportError:
    LLMEngine = None  # type: ignore[assignment,misc]
    _LLM_AVAILABLE = False

# `vision.capture` / `vision.model` depend on the optional "vision" extra
# (mss, onnxruntime, huggingface_hub, tokenizers) — see pyproject.toml and
# docs/DECISIONS.md. Same defensive-import treatment as voice/llm above —
# Iris still launches without it, just without screen-context awareness.
# Screen capture is additionally gated behind `settings.vision.enabled`
# (opt-in, off by default) even when the extra IS installed — see
# `config/schema.py:VisionSettings`.
try:
    from vision.capture import ScreenCapture
    from vision.model import VisionModel
    from vision.ocr import OCRReader

    _VISION_AVAILABLE = True
except ImportError:
    ScreenCapture = None  # type: ignore[assignment,misc]
    VisionModel = None  # type: ignore[assignment,misc]
    OCRReader = None  # type: ignore[assignment,misc]
    _VISION_AVAILABLE = False


def _percent_box_to_pixels(
    location, image_size: tuple[int, int], monitor_left: int, monitor_top: int
) -> tuple[int, int, int, int]:
    """Convert a `VisionModel.locate()` result (percent of the captured
    image, 0-100 each) to real screen pixel coordinates.

    `image_size` is the captured screenshot's own resolution (`PIL.Image
    .size`), which `x`/`y`/`w`/`h` are percentages of --  not necessarily
    the same as the on-screen monitor resolution in a scaled-DPI setup,
    but assumed equal here (same assumption `vision/capture.py` already
    makes -- see its `mss`-based `capture()`). `monitor_left`/
    `monitor_top` offset the result to real screen coordinates -- both
    0 unless `vision.monitor_index` selects something other than the
    combined virtual screen (index 0).

    Milestone 7, Part B.3. Pure/no side effects so it's unit-testable on
    its own, unlike the rest of this file's wiring (see module docstring:
    "no feature logic belongs here" -- this is the one piece of actual
    arithmetic Part B.3 needed, kept as small and isolated as possible).
    """
    img_w, img_h = image_size
    x = monitor_left + round(location.x / 100 * img_w)
    y = monitor_top + round(location.y / 100 * img_h)
    w = round(location.w / 100 * img_w)
    h = round(location.h / 100 * img_h)
    return x, y, w, h


def main() -> int:
    settings = get_settings()
    setup_logging(settings.logging)

    logger.info("Starting %s v%s", settings.app_name, settings.version)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.version)

    # Real Aura rendering (Milestone 6): a soft ambient screen-edge glow,
    # replacing the placeholder NullAuraRenderer. Falls back to
    # NullAuraRenderer on any construction/initialize failure -- same
    # graceful-degradation shape as the LLM/vision pipelines above, since a
    # missing visual is far less important than Iris staying usable at all.
    try:
        renderer = GlowAuraRenderer()
        aura = AuraController(renderer=renderer)
        aura.start()
    except Exception:
        logger.exception("Could not start the Aura glow renderer — falling back to no visuals.")
        aura = AuraController(renderer=NullAuraRenderer())
        aura.start()

    # Bridges: audio/worker threads -> Qt main thread. See
    # app/wake_word_bridge.py, app/transcript_bridge.py, and
    # app/llm_bridge.py.
    wake_word_bridge = WakeWordBridge()
    transcript_bridge = TranscriptBridge()
    llm_bridge = LLMResponseBridge()
<<<<<<< HEAD
    vision_locate_bridge = VisionLocateBridge()
=======
    locate_bridge = LocateResultBridge()
>>>>>>> 5b2c291bc460334a015110c8d96fb071ae4ebdcd

    # Loaded eagerly (like the wake word / Whisper models) so the first
    # real utterance isn't delayed by a cold-start model load. Failure here
    # is NOT fatal to the whole app — same graceful-degradation pattern as
    # VoiceActivationService's transcriber load in voice/service.py.
    llm_engine = None
    if _LLM_AVAILABLE:
        try:
            llm_engine = LLMEngine(
                repo_id=settings.llm.repo_id,
                filename=settings.llm.filename,
                local_model_path=settings.llm.local_model_path,
                n_ctx=settings.llm.n_ctx,
                n_gpu_layers=settings.llm.n_gpu_layers,
                system_prompt=settings.llm.system_prompt,
            )
        except RuntimeError:
            logger.exception("Could not load the LLM — continuing without generated responses.")
            llm_engine = None
    else:
        logger.warning(
            "LLM dependencies not installed (pip install -e '.[llm]') — "
            "continuing without generated responses this session."
        )

    # Screen-context awareness (Milestone 5): opt-in via settings.vision.enabled
    # (default False) on top of the usual extra-installed check, so installing
    # the vision extra alone never causes a screenshot to be taken — see
    # docs/DECISIONS.md. Loaded eagerly, same graceful-degradation shape as
    # the LLM above: a failed model load leaves vision_model = None rather
    # than crashing, and _generate_worker simply skips the screen-context step.
    screen_capture = None
    vision_model = None
    ocr_reader = None
    if not settings.vision.enabled:
        logger.info("Screen-context awareness disabled (vision.enabled=false in config).")
    elif _VISION_AVAILABLE:
        screen_capture = ScreenCapture(monitor_index=settings.vision.monitor_index)
        try:
            vision_model = VisionModel(
                repo_id=settings.vision.repo_id,
                model_filename=settings.vision.model_filename,
                mmproj_filename=settings.vision.mmproj_filename,
                local_model_path=settings.vision.local_model_path,
                local_mmproj_path=settings.vision.local_mmproj_path,
                n_ctx=settings.vision.n_ctx,
                n_gpu_layers=settings.vision.n_gpu_layers,
            )
        except RuntimeError:
            logger.exception(
                "Could not load the vision model — continuing without screen context."
            )
            vision_model = None

        # OCR is independent of the scene-description model above -- a
        # failure here (e.g. Tesseract binary not installed) shouldn't take
        # down scene description, and vice versa. See vision/ocr.py.
        if settings.vision.ocr_enabled:
            try:
                ocr_reader = OCRReader(
                    tesseract_cmd=settings.vision.tesseract_cmd,
                    min_confidence=settings.vision.ocr_min_confidence,
                )
            except RuntimeError:
                logger.exception(
                    "Could not load the OCR reader — continuing without verbatim on-screen text."
                )
                ocr_reader = None
    else:
        logger.warning(
            "Vision dependencies not installed (pip install -e '.[vision]') — "
            "continuing without screen context this session."
        )

    # Milestone 7, Part B.3: real on-screen offset of the monitor being
    # captured, so locate()'s percent-of-image coordinates can be converted
    # to real screen pixels (see _percent_box_to_pixels). Stays (0, 0) --
    # correct for monitor_index=0 (the combined virtual screen, the
    # default) -- if this lookup fails for any reason; a wrong offset on a
    # genuine multi-monitor, non-default monitor_index setup would show
    # the target box in the wrong place, but that's a lesser failure than
    # crashing startup over it.
    vision_monitor_left = 0
    vision_monitor_top = 0
    if screen_capture is not None:
        try:
            monitor = ScreenCapture.list_monitors()[settings.vision.monitor_index]
            vision_monitor_left = monitor["left"]
            vision_monitor_top = monitor["top"]
        except Exception:
            logger.exception(
                "Could not determine monitor geometry for target-box pixel "
                "conversion — falling back to a (0, 0) offset."
            )

    def on_wake_word_detected(model_name: str, score: float) -> None:
        # Runs on the main thread (Qt queues the signal delivery for us).
        logger.info("Wake word '%s' detected (score=%.3f) — Aura -> LISTENING", model_name, score)
        aura.set_state(AuraState.LISTENING)

    def _build_prompt_with_screen_context(text: str) -> str | None:
        # Runs on the same worker thread as generation (see _generate_worker).
        # Capture + captioning happen here, not on the Qt main thread, for
        # the same reason LLM generation does — this can take real time
        # (captioning is CPU-bound greedy decoding, see vision/model.py).
        # Any failure here is logged and swallowed — screen context is a
        # nice-to-have, never worth failing the whole query over.
        #
        # Returns None (Milestone 7, Part B.3) specifically when
        # locate() reports found=False or a parse failure for a query
        # that asked to find/point at something (locate_trigger_keywords
        # matched) -- that case aborts the whole query with a retry
        # prompt instead of falling back to a captionless answer. Every
        # other failure path here (capture failure, model load failure,
        # no keyword match) still just degrades to returning `text`
        # unchanged, as before.
        if screen_capture is None or (vision_model is None and ocr_reader is None):
            return text

        vision_keywords = settings.vision.trigger_keywords
        should_caption_or_ocr = not vision_keywords or any(
            kw.lower() in text.lower() for kw in vision_keywords
        )

        locate_keywords = settings.vision.locate_trigger_keywords
        should_locate = vision_model is not None and (
            not locate_keywords or any(kw.lower() in text.lower() for kw in locate_keywords)
        )

        if not should_caption_or_ocr and not should_locate:
            logger.debug(
                "Skipping screen context — query matched neither "
                "vision.trigger_keywords %r nor vision.locate_trigger_keywords %r",
                vision_keywords,
                locate_keywords,
            )
            return text
        logger.debug(
            "Screen context triggered for query %r (locate=%s, caption/ocr=%s)",
            text,
            should_locate,
            should_caption_or_ocr,
        )

        try:
            image = screen_capture.capture()
        except Exception:
            logger.exception("Screen capture failed — continuing without screen context.")
            return text

        # Milestone 7, Part B.3: attempt to find and flash a target box
        # before captioning/OCR. found=False and a genuine parse failure
        # are treated identically here, per the Milestone 7 design
        # decision — both abort this query with a retry prompt rather
        # than silently falling back to a normal answer, since the user
        # specifically asked to be shown something.
        if should_locate:
            try:
                location = vision_model.locate(image, text)
            except Exception:
                logger.exception("Vision locate() failed — continuing without a target box.")
                location = None

            if location is not None and location.found:
                px, py, pw, ph = _percent_box_to_pixels(
                    location, image.size, vision_monitor_left, vision_monitor_top
                )
                logger.info(
                    "locate() found %r at screen pixels (%d, %d, %d, %d)",
                    location.label,
                    px,
                    py,
                    pw,
                    ph,
                )
                vision_locate_bridge.report_found(px, py, pw, ph)
            else:
                logger.info(
                    "locate() found nothing to point at for query %r (label=%r) "
                    "— aborting this query with a retry prompt.",
                    text,
                    location.label if location is not None else None,
                )
                llm_bridge.report_failure(
                    "I couldn't find anything on screen matching that — want to try again?"
                )
                return None

        if not should_caption_or_ocr:
            return text

        caption = ""
        if vision_model is not None:
            try:
                caption = vision_model.describe(
                    image,
                    prompt=settings.vision.caption_prompt,
                    max_tokens=settings.vision.max_tokens,
                )
            except Exception:
                logger.exception("Screen captioning failed — continuing without scene description.")

        ocr_text = ""
        if ocr_reader is not None:
            try:
                ocr_text = ocr_reader.read(image)
            except Exception:
                logger.exception("OCR failed — continuing without verbatim on-screen text.")

        if not caption and not ocr_text:
            return text

        context_lines = []
        if caption:
            context_lines.append(f"Screen description: {caption}")
        if ocr_text:
            context_lines.append(f"Verbatim text on screen: {ocr_text}")
        context = "\n".join(context_lines)

        logger.debug("Screen context added to prompt: %r", context)
        return f"[{context}]\n\nUser: {text}"

    def _is_locate_query(text: str) -> bool:
        # Milestone 7 (Part B.3): a separate, more specific gate than
        # trigger_keywords above -- trigger_keywords decides "does this
        # query care about the screen at all," this decides "does this
        # query want Iris to point at something," which uses the vision
        # model's structured locate() output + Aura's target-box morph
        # instead of normal LLM generation. Checked independently of
        # trigger_keywords -- a locate query doesn't also need to match
        # the caption-gating keywords.
        keywords = settings.vision.locate_trigger_keywords
        return bool(keywords) and any(kw.lower() in text.lower() for kw in keywords)

    def _locate_worker(text: str) -> None:
        # Runs on a dedicated worker thread, same reasoning as
        # _generate_worker -- MiniCPM-V inference is real, CPU-bound
        # time and must never run on the audio callback or Qt main
        # thread. Delivers its result back via locate_bridge.
        assert vision_model is not None and screen_capture is not None
        try:
            image = screen_capture.capture()
        except Exception:
            logger.exception("Screen capture failed during locate() — reporting not-found.")
            locate_bridge.report_not_found()
            return

        try:
            # The full query text is passed as the target description
            # as-is (e.g. "where is the save button") rather than
            # stripping the matched trigger phrase first -- simplest
            # thing that works for a first pass; DEFAULT_LOCATE_PROMPT
            # already frames it as "find this," so the extra words don't
            # confuse the prompt, just add a little noise to it.
            location = vision_model.locate(image, target=text)
        except Exception:
            logger.exception("VisionModel.locate() failed — reporting not-found.")
            locate_bridge.report_not_found()
            return

        # found=False and a parse failure (location is None) are one
        # path, not two -- see docs/DECISIONS.md.
        if location is None or not location.found:
            logger.info(
                "locate() found nothing for target %r (parse_failure=%s).",
                text,
                location is None,
            )
            locate_bridge.report_not_found()
            return

        # Sanity-check the box itself -- the grammar guarantees valid
        # JSON shape, not a semantically real answer (see locate()'s own
        # docstring). A model can report found=True with w=0 and/or h=0
        # (or, in principle, any degenerate combination) when it's
        # actually unable to locate the target -- this is NOT the same
        # failure mode as found=False, but the caller still needs to
        # treat it as "nothing to point at," rather than letting
        # GlowAuraRenderer's own bounds-clamping (Part B.2, which only
        # guards against off-screen/undersized coordinates, not
        # zero-area ones) quietly inflate a meaningless (0,0) corner box
        # up to MIN_BOX_SIZE_PX and present it as if it were real.
        if location.w <= 0 or location.h <= 0:
            logger.warning(
                "locate() reported found=True for %r but with a degenerate "
                "zero-area box (label=%r, x=%d, y=%d, w=%d, h=%d) -- "
                "treating as not-found rather than rendering a meaningless box.",
                text,
                location.label,
                location.x,
                location.y,
                location.w,
                location.h,
            )
            locate_bridge.report_not_found()
            return

        # A found=True box covering (almost) the entire screenshot is the
        # opposite degenerate case from a zero-area one, but just as
        # meaningless to point at -- "the whole screen" isn't an answer to
        # "point at X," and morphing Aura's outline to trace the full
        # screen edge is visually indistinguishable from its own idle
        # state, so this would silently look like nothing happened.
        # w/h are already percentages (0-100) of the image, so w*h is
        # the box's area as a percent of the total image area.
        box_area_pct = location.w * location.h
        if box_area_pct >= LOCATE_MAX_BOX_AREA_PCT:
            logger.warning(
                "locate() reported found=True for %r but with a near-"
                "full-image box (label=%r, x=%d, y=%d, w=%d, h=%d, "
                "area=%d%% of image) -- treating as not-found rather than "
                "rendering a meaningless whole-screen box.",
                text,
                location.label,
                location.x,
                location.y,
                location.w,
                location.h,
                box_area_pct,
            )
            locate_bridge.report_not_found()
            return

        geometry = screen_capture.monitor_geometry
        if geometry is None:
            # Shouldn't happen -- capture() above always sets it on
            # success -- but degrade to not-found rather than crash or
            # guess at screen geometry if it somehow is.
            logger.error("No monitor_geometry available after a successful capture() — reporting not-found.")
            locate_bridge.report_not_found()
            return

        # Convert locate()'s percent-of-screenshot (0-100) coordinates to
        # real screen pixels using the geometry of the monitor/region
        # that was actually captured. GlowAuraRenderer's overlay now spans
        # the full virtual desktop (the union of every screen), matching
        # what vision.monitor_index=0 captures, so these pixel coordinates
        # land in the same coordinate space the overlay actually covers --
        # previously the overlay was primary-screen-only, which silently
        # clamped correctly-computed boxes onto the wrong monitor. See
        # docs/DECISIONS.md.
        mon_left = geometry["left"]
        mon_top = geometry["top"]
        mon_width = geometry["width"]
        mon_height = geometry["height"]
        x = mon_left + round(location.x / 100 * mon_width)
        y = mon_top + round(location.y / 100 * mon_height)
        w = round(location.w / 100 * mon_width)
        h = round(location.h / 100 * mon_height)

        logger.info(
            "locate() found %r at percent(%d,%d,%d,%d) -> pixels(%d,%d,%d,%d).",
            location.label,
            location.x,
            location.y,
            location.w,
            location.h,
            x,
            y,
            w,
            h,
        )
        locate_bridge.report_found(x, y, w, h, location.label)

    def _generate_worker(text: str) -> None:
        # Runs on a dedicated worker thread — never the audio callback
        # thread or the Qt main thread, same reasoning as transcription
        # (see docs/DECISIONS.md). Delivers its result back via llm_bridge.
        assert llm_engine is not None  # only started when it loaded successfully
        try:
            prompt = _build_prompt_with_screen_context(text)
            if prompt is None:
                # Milestone 7, Part B.3: locate() found nothing to point
                # at for this query. The retry-prompt failure was already
                # reported via llm_bridge.report_failure() inside
                # _build_prompt_with_screen_context — nothing left to do
                # here except stop before spending an LLM call on a query
                # we've already decided not to answer normally.
                return
            response = llm_engine.generate(
                prompt,
                max_tokens=settings.llm.max_tokens,
                temperature=settings.llm.temperature,
            )
            if response:
                llm_bridge.report_response(response)
            else:
                llm_bridge.report_failure("LLM returned an empty response.")
        except Exception as exc:
            logger.exception("LLM generation failed.")
            llm_bridge.report_failure(str(exc))

    def on_transcribed(text: str) -> None:
        # Runs on the main thread. Keeps Aura in THINKING while a worker
        # thread handles the query; on_llm_response / on_llm_failed /
        # on_target_found / on_target_not_found bring it back to IDLE (or
        # ERROR) once that's done.
        logger.info('Transcribed: "%s" — Aura -> THINKING', text)
        aura.set_state(AuraState.THINKING)

        # Milestone 7 (Part B.3): a locate-triggered query ("where is the
        # save button") bypasses normal LLM generation entirely -- the
        # vision model's structured locate() output is itself the answer
        # (a box to point at), not something that needs the text LLM's
        # help interpreting. See docs/DECISIONS.md.
        if vision_model is not None and screen_capture is not None and _is_locate_query(text):
            logger.debug("Locate-triggered query matched vision.locate_trigger_keywords: %r", text)
            threading.Thread(target=_locate_worker, args=(text,), daemon=True).start()
            return

        if llm_engine is None:
            logger.warning("No LLM available — skipping generation.")
            window.show_response("(No LLM available this session — see logs.)")
            aura.set_state(AuraState.IDLE)
            return

        threading.Thread(target=_generate_worker, args=(text,), daemon=True).start()

    def on_llm_response(text: str) -> None:
        # Runs on the main thread.
        logger.info('LLM response ready (%d chars) — Aura -> IDLE', len(text))
        window.show_response(text)
        aura.set_state(AuraState.IDLE)

    def on_llm_failed(message: str) -> None:
        # Runs on the main thread.
        logger.error("LLM generation failed: %s", message)
        window.show_response(f"(LLM error — see logs: {message})")
        aura.set_state(AuraState.ERROR)

    def on_target_found(x: int, y: int, w: int, h: int, label: str) -> None:
        # Runs on the main thread. Geometry (the target box) and color
        # (AuraState) are orthogonal -- see aura/renderer/glow_renderer.py
        # -- so this both morphs Aura's outline to the found element AND
        # brings its color back to IDLE, independently.
        logger.info("Target found (%r) — Aura -> show_target_box + IDLE", label)
        aura.show_target_box(x, y, w, h)
        window.show_response(f"Found it — {label}." if label else "Found it.")
        aura.set_state(AuraState.IDLE)

    def on_target_not_found() -> None:
        # Runs on the main thread. found=False and a parse failure are
        # one path, not two -- see docs/DECISIONS.md.
        logger.info("Target not found — Aura -> ERROR")
        window.show_response("I couldn't find that — want to try again?")
        aura.set_state(AuraState.ERROR)

    def on_no_speech_detected() -> None:
        # Runs on the main thread. Wake word fired but nothing was said
        # (or transcription was unavailable) — just go back to idle.
        logger.info("No speech recognized — Aura -> IDLE")
        aura.set_state(AuraState.IDLE)

    def on_target_box_found(x: int, y: int, w: int, h: int) -> None:
        # Runs on the main thread. Milestone 7, Part B.3: locate() found
        # something on the worker thread — the actual Aura call has to
        # happen here, since AuraController/GlowAuraRenderer own real Qt
        # widgets. Geometry only, orthogonal to AuraState — doesn't touch
        # whatever THINKING/IDLE/ERROR transition is happening alongside it.
        logger.info("Aura target box -> (%d, %d, %d, %d)", x, y, w, h)
        aura.show_target_box(x, y, w, h)

    wake_word_bridge.detected.connect(on_wake_word_detected)
    transcript_bridge.transcribed.connect(on_transcribed)
    transcript_bridge.no_speech_detected.connect(on_no_speech_detected)
    llm_bridge.response_ready.connect(on_llm_response)
    llm_bridge.generation_failed.connect(on_llm_failed)
<<<<<<< HEAD
    vision_locate_bridge.box_found.connect(on_target_box_found)
=======
    locate_bridge.target_found.connect(on_target_found)
    locate_bridge.target_not_found.connect(on_target_not_found)
>>>>>>> 5b2c291bc460334a015110c8d96fb071ae4ebdcd

    voice_service = None
    if _VOICE_AVAILABLE:
        voice_service = VoiceActivationService(
            voice_settings=settings.voice,
            speech_settings=settings.speech,
            on_wake_word=wake_word_bridge.report_detection,
            on_transcript=transcript_bridge.report_transcript,
        )
        if not voice_service.start():
            logger.warning("Continuing without voice activation this session (see error above).")
            aura.set_state(AuraState.ERROR)
    else:
        logger.warning(
            "Voice activation dependencies not installed (pip install -e '.[speech]') — "
            "continuing without wake word detection this session."
        )

    window = MainWindow(
        app_name=settings.app_name,
        app_version=settings.version,
        debug_enabled=settings.debug.enabled,
    )
    window.show()

    def on_debug_text_submitted(text: str) -> None:
        # Drives the exact same handling path real voice input would:
        # a synthetic "wake word" event, then the typed text as if it were
        # the transcription result. Now also exercises the LLM the same
        # way real voice input would.
        logger.info('Debug text input treated as a voice command: "%s"', text)
        on_wake_word_detected("debug_text_input", 1.0)
        on_transcribed(text)

    window.debug_text_submitted.connect(on_debug_text_submitted)

    exit_code = app.exec()

    if voice_service is not None:
        voice_service.stop()
    aura.stop()
    logger.info("%s exited with code %s", settings.app_name, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
